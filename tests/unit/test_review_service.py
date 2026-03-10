from __future__ import annotations

from uuid import UUID

import pytest
from autolab.agents import ReviewAgentReply, ReviewAgentRequest, ReviewRuntimeUnavailableError
from autolab.campaigns import ReviewService
from autolab.core.enums import (
    ArtifactType,
    CampaignMode,
    ReviewParticipantType,
    ReviewRoundMode,
    ReviewRoundStatus,
    ReviewStatus,
    RunStatus,
    SimulatorKind,
)
from autolab.core.models import (
    AgentDecision,
    ArtifactRecord,
    Campaign,
    CampaignBudget,
    Candidate,
    Objective,
    ReviewArtifactLink,
    ReviewParticipant,
    ReviewThread,
    SearchSpace,
    SearchSpaceDimension,
    SimulationRun,
)
from autolab.core.settings import get_settings
from autolab.storage import (
    ArtifactRepository,
    ArtifactStore,
    CampaignRepository,
    DecisionRepository,
    ReviewRepository,
    RunRepository,
    init_db,
)
from autolab.storage.db import session_scope


class StubReviewRunner:
    def __init__(self) -> None:
        self.requests: list[ReviewAgentRequest] = []

    def run(self, request: ReviewAgentRequest) -> ReviewAgentReply:
        self.requests.append(request)
        recommendation = ReviewStatus.OPEN
        if request.agent_name == "workflow_agent":
            recommendation = ReviewStatus.APPROVED
        return ReviewAgentReply(
            summary=f"{request.agent_name} summary",
            rationale=f"{request.agent_name} rationale",
            recommendation=recommendation,
            concerns=["none"],
            next_steps=["ship it"],
        )


def _seed_campaign_run_and_artifact() -> tuple[Campaign, SimulationRun, ArtifactRecord]:
    settings = get_settings()
    init_db(settings)
    store = ArtifactStore(settings)
    campaign = Campaign(
        name="review-campaign",
        mode=CampaignMode.MATERIALS_DISCOVERY,
        objectives=[Objective(name="score", metric_key="score", direction="maximize")],
        search_space=SearchSpace(
            dimensions=[
                SearchSpaceDimension(name="x", kind="continuous", lower=0.0, upper=1.0)
            ]
        ),
        budget=CampaignBudget(max_runs=3, batch_size=1, max_failures=1),
        simulator=SimulatorKind.LAMMPS,
    )
    candidate = Candidate(campaign_id=campaign.id, values={"x": 0.5})
    run = SimulationRun(
        campaign_id=campaign.id,
        candidate_id=candidate.id,
        simulator=SimulatorKind.LAMMPS,
        status=RunStatus.SUCCEEDED,
        metrics={"score": 0.91},
        metadata={"workflow_name": "test-workflow"},
    )
    artifact = store.write_text(
        campaign.id,
        run.id,
        ArtifactType.SUMMARY,
        "reports/review-summary.json",
        '{"score": 0.91, "note": "stable"}',
    )
    with session_scope(settings) as session:
        campaigns = CampaignRepository(session)
        runs = RunRepository(session)
        artifacts = ArtifactRepository(session)
        decisions = DecisionRepository(session)
        campaigns.create(campaign)
        runs.create_candidate(candidate)
        runs.create_run(run)
        campaigns.save_summary(campaign.id, "critic", "Recent experiments look stable.", run.id)
        decisions.create(
            AgentDecision(
                campaign_id=campaign.id,
                run_id=run.id,
                agent_name="critic_agent",
                action="summarize_recent_runs",
                rationale="The objective improved and no constraint failed.",
                structured_output={"trend": "positive"},
            )
        )
        artifacts.create(artifact)
    return campaign, run, artifact


def test_review_repository_returns_detail_with_links() -> None:
    settings = get_settings()
    init_db(settings)
    campaign, run, artifact = _seed_campaign_run_and_artifact()
    with session_scope(settings) as session:
        reviews = ReviewRepository(session)
        thread = reviews.create_thread(
            ReviewThread(
                campaign_id=campaign.id,
                run_id=run.id,
                title="Repository detail review",
                objective="Check repository round-tripping.",
                created_by="alice",
            )
        )
        reviews.upsert_participant(
            ReviewParticipant(
                review_id=thread.id,
                participant_key="analysis_agent",
                participant_type=ReviewParticipantType.AGENT,
                role_label="analysis_agent",
            )
        )
        reviews.create_artifact_link(
            ReviewArtifactLink(review_id=thread.id, artifact_id=artifact.id)
        )
        detail = reviews.get_thread_detail(thread.id)
        assert detail is not None
        assert detail.participants
        assert detail.artifact_ids == [artifact.id]
        assert detail.run_id == run.id


def test_execute_moderated_review_round_persists_agent_posts_and_context() -> None:
    settings = get_settings()
    runner = StubReviewRunner()
    service = ReviewService(settings, review_runner=runner)
    campaign, run, artifact = _seed_campaign_run_and_artifact()

    review = service.create_review(
        campaign.id,
        title="Run review",
        objective="Assess whether the run is ready for approval.",
        created_by="alice",
        run_id=run.id,
        artifact_ids=[artifact.id],
    )
    round_record = service.create_round(
        review.id,
        mode=ReviewRoundMode.MODERATED_PANEL,
        participant_keys=None,
        queued=False,
    )
    executed = service.execute_round(review.id, round_record.id)

    assert executed.status == ReviewRoundStatus.COMPLETED
    assert executed.recommendation == ReviewStatus.APPROVED
    posts = service.list_posts(review.id)
    assert [post.author_key for post in posts] == [
        "analysis_agent",
        "critic_agent",
        "planner_agent",
        "workflow_agent",
    ]
    assert runner.requests[0].context_bundle["linked_artifacts"][0]["inline_content"]
    assert runner.requests[0].context_bundle["summaries"]
    assert runner.requests[0].context_bundle["decisions"]
    review_detail = service.get_review(review.id)
    assert review_detail is not None
    assert review_detail.status == ReviewStatus.APPROVED


def test_create_review_rejects_invalid_artifact_link() -> None:
    settings = get_settings()
    service = ReviewService(settings, review_runner=StubReviewRunner())
    campaign, run, _ = _seed_campaign_run_and_artifact()

    with pytest.raises(ValueError, match="linked artifacts"):
        service.create_review(
            campaign.id,
            title="Bad review",
            objective="Should fail",
            created_by="alice",
            run_id=run.id,
            artifact_ids=[UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")],
        )


def test_execute_round_marks_failure_and_persists_system_post_when_runtime_unavailable() -> None:
    settings = get_settings()
    service = ReviewService(settings)
    campaign, run, artifact = _seed_campaign_run_and_artifact()
    review = service.create_review(
        campaign.id,
        title="Runtime failure review",
        objective="Demonstrate runtime failure handling.",
        created_by="alice",
        run_id=run.id,
        artifact_ids=[artifact.id],
    )
    round_record = service.create_round(
        review.id,
        mode=ReviewRoundMode.SINGLE_PASS,
        participant_keys=["workflow_agent"],
        queued=False,
    )

    with pytest.raises(ReviewRuntimeUnavailableError):
        service.execute_round(review.id, round_record.id)

    detail = service.get_review(review.id)
    assert detail is not None
    assert detail.status == ReviewStatus.OPEN
    failed_round = next(
        round_item for round_item in detail.rounds if round_item.id == round_record.id
    )
    assert failed_round.status == ReviewRoundStatus.FAILED
    posts = service.list_posts(review.id)
    assert posts[-1].author_type == ReviewParticipantType.SYSTEM
    assert "failed" in posts[-1].body.lower()


def test_create_round_rejects_resolved_review() -> None:
    settings = get_settings()
    service = ReviewService(settings, review_runner=StubReviewRunner())
    campaign, run, artifact = _seed_campaign_run_and_artifact()
    review = service.create_review(
        campaign.id,
        title="Resolved review",
        objective="No more rounds allowed after resolution.",
        created_by="alice",
        run_id=run.id,
        artifact_ids=[artifact.id],
    )
    service.resolve_review(
        review.id,
        status=ReviewStatus.RESOLVED,
        resolution_summary="The thread is done.",
    )

    with pytest.raises(ValueError, match="resolved"):
        service.create_round(
            review.id,
            mode=ReviewRoundMode.MODERATED_PANEL,
            participant_keys=None,
            queued=False,
        )
