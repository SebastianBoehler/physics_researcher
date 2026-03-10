from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from autolab.agents import (
    ReviewAgentRequest,
    ReviewAgentRunner,
    ReviewRuntimeUnavailableError,
    default_review_participants,
    normalize_moderated_participants,
)
from autolab.core.enums import (
    ArtifactType,
    ReviewParticipantType,
    ReviewRoundMode,
    ReviewRoundStatus,
    ReviewStatus,
)
from autolab.core.models import (
    ReviewArtifactLink,
    ReviewParticipant,
    ReviewPost,
    ReviewRound,
    ReviewThread,
    ReviewThreadDetail,
)
from autolab.core.settings import Settings
from autolab.storage import (
    ArtifactRepository,
    ArtifactStore,
    CampaignRepository,
    DecisionRepository,
    ReviewRepository,
    RunRepository,
    SummaryRepository,
)
from autolab.storage.db import session_scope
from autolab.telemetry import get_logger

logger = get_logger(__name__)

_INLINE_TEXT_MEDIA_TYPES = {
    "application/json",
    "application/ld+json",
    "application/xml",
    "text/markdown",
}
_INLINE_TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".markdown",
    ".txt",
    ".csv",
    ".yaml",
    ".yml",
    ".xml",
    ".log",
}
_MAX_INLINE_ARTIFACT_BYTES = 64 * 1024


class ReviewService:
    def __init__(self, settings: Settings, review_runner: ReviewAgentRunner | None = None) -> None:
        self._settings = settings
        self._review_runner = review_runner or ReviewAgentRunner(settings)
        self._artifact_store = ArtifactStore(settings)

    def create_review(
        self,
        campaign_id: UUID,
        *,
        title: str,
        objective: str,
        created_by: str,
        run_id: UUID | None = None,
        artifact_ids: list[UUID] | None = None,
        participants: list[ReviewParticipant] | None = None,
    ) -> ReviewThreadDetail:
        with session_scope(self._settings) as session:
            campaigns = CampaignRepository(session)
            runs = RunRepository(session)
            artifacts = ArtifactRepository(session)
            reviews = ReviewRepository(session)
            campaign = campaigns.get(campaign_id)
            if campaign is None:
                msg = f"campaign {campaign_id} not found"
                raise KeyError(msg)
            if run_id is not None:
                run = runs.get_run(run_id)
                if run is None or run.campaign_id != campaign_id:
                    msg = f"run {run_id} does not belong to campaign {campaign_id}"
                    raise ValueError(msg)
            linked_artifacts = artifacts.list_by_ids(artifact_ids or [])
            if len(linked_artifacts) != len(artifact_ids or []):
                msg = "one or more linked artifacts were not found"
                raise ValueError(msg)
            if any(artifact.campaign_id != campaign_id for artifact in linked_artifacts):
                msg = "linked artifacts must belong to the same campaign"
                raise ValueError(msg)

            review = ReviewThread(
                campaign_id=campaign_id,
                run_id=run_id,
                title=title,
                objective=objective,
                created_by=created_by,
            )
            reviews.create_thread(review)
            reviews.upsert_participant(
                ReviewParticipant(
                    review_id=review.id,
                    participant_key=created_by,
                    participant_type=ReviewParticipantType.HUMAN,
                    role_label="researcher",
                )
            )
            for participant in participants or []:
                reviews.upsert_participant(
                    participant.model_copy(update={"review_id": review.id})
                )
            for artifact in linked_artifacts:
                reviews.create_artifact_link(
                    ReviewArtifactLink(review_id=review.id, artifact_id=artifact.id)
                )
            detail = reviews.get_thread_detail(review.id)
            assert detail is not None
            return detail

    def list_reviews(self, campaign_id: UUID, run_id: UUID | None = None) -> list[ReviewThread]:
        with session_scope(self._settings) as session:
            return ReviewRepository(session).list_threads(campaign_id, run_id=run_id)

    def get_review(self, review_id: UUID) -> ReviewThreadDetail | None:
        with session_scope(self._settings) as session:
            return ReviewRepository(session).get_thread_detail(review_id)

    def list_posts(self, review_id: UUID) -> list[ReviewPost]:
        with session_scope(self._settings) as session:
            return ReviewRepository(session).list_posts(review_id)

    def add_post(
        self,
        review_id: UUID,
        *,
        author_key: str,
        author_type: ReviewParticipantType,
        body: str,
        role_label: str | None = None,
        parent_post_id: UUID | None = None,
        round_id: UUID | None = None,
        structured_payload: dict[str, Any] | None = None,
    ) -> ReviewPost:
        with session_scope(self._settings) as session:
            reviews = ReviewRepository(session)
            detail = reviews.get_thread_detail(review_id)
            if detail is None:
                msg = f"review {review_id} not found"
                raise KeyError(msg)
            if parent_post_id is not None:
                parent_ids = {post.id for post in reviews.list_posts(review_id)}
                if parent_post_id not in parent_ids:
                    msg = f"parent post {parent_post_id} does not belong to review {review_id}"
                    raise ValueError(msg)
            reviews.upsert_participant(
                ReviewParticipant(
                    review_id=review_id,
                    participant_key=author_key,
                    participant_type=author_type,
                    role_label=role_label or self._default_role_label(author_key, author_type),
                )
            )
            post = ReviewPost(
                review_id=review_id,
                round_id=round_id,
                parent_post_id=parent_post_id,
                author_key=author_key,
                author_type=author_type,
                body=body,
                structured_payload=structured_payload or {},
            )
            return reviews.create_post(post)

    def create_round(
        self,
        review_id: UUID,
        *,
        mode: ReviewRoundMode,
        participant_keys: list[str] | None = None,
        queued: bool,
    ) -> ReviewRound:
        with session_scope(self._settings) as session:
            reviews = ReviewRepository(session)
            detail = reviews.get_thread_detail(review_id)
            if detail is None:
                msg = f"review {review_id} not found"
                raise KeyError(msg)
            if detail.status == ReviewStatus.RESOLVED:
                msg = f"review {review_id} is already resolved"
                raise ValueError(msg)
            resolved_participants = self._resolve_round_participants(
                mode,
                participant_keys=participant_keys,
                run_attached=detail.run_id is not None,
            )
            for participant_key in resolved_participants:
                reviews.upsert_participant(
                    ReviewParticipant(
                        review_id=review_id,
                        participant_key=participant_key,
                        participant_type=ReviewParticipantType.AGENT,
                        role_label=participant_key,
                    )
                )
            detail.status = ReviewStatus.IN_REVIEW
            detail.updated_at = datetime.now(UTC)
            reviews.update_thread(detail)
            round_record = ReviewRound(
                review_id=review_id,
                mode=mode,
                status=ReviewRoundStatus.QUEUED if queued else ReviewRoundStatus.RUNNING,
                participant_keys=resolved_participants,
                started_at=None if queued else datetime.now(UTC),
            )
            return reviews.create_round(round_record)

    def execute_round(self, review_id: UUID, round_id: UUID) -> ReviewRound:
        context_bundle, prior_posts, round_record, review = self._prepare_round_execution(
            review_id, round_id
        )
        try:
            replies: list[tuple[str, dict[str, Any]]] = []
            for participant_key in round_record.participant_keys:
                reply = self._review_runner.run(
                    ReviewAgentRequest(
                        agent_name=participant_key,
                        objective=review.objective,
                        context_bundle=context_bundle,
                        prior_posts=prior_posts,
                    )
                )
                replies.append((participant_key, reply.model_dump(mode="json")))
                prior_posts.append(
                    {
                        "author_key": participant_key,
                        "author_type": ReviewParticipantType.AGENT.value,
                        "body": reply.summary,
                        "structured_payload": reply.model_dump(mode="json"),
                    }
                )
            recommendation = (
                ReviewStatus(replies[-1][1]["recommendation"]) if replies else ReviewStatus.OPEN
            )
            with session_scope(self._settings) as session:
                reviews = ReviewRepository(session)
                current_round = reviews.get_round(round_id)
                current_review = reviews.get_thread(review_id)
                if current_round is None or current_review is None:
                    msg = "review or review round disappeared during execution"
                    raise KeyError(msg)
                for participant_key, payload in replies:
                    reviews.create_post(
                        ReviewPost(
                            review_id=review_id,
                            round_id=round_id,
                            author_key=participant_key,
                            author_type=ReviewParticipantType.AGENT,
                            body=str(payload["summary"]),
                            structured_payload=payload,
                        )
                    )
                current_round.status = ReviewRoundStatus.COMPLETED
                current_round.recommendation = recommendation
                current_round.metadata = {"reply_count": len(replies)}
                current_round.completed_at = datetime.now(UTC)
                reviews.update_round(current_round)
                if recommendation != ReviewStatus.RESOLVED:
                    current_review.status = recommendation
                current_review.updated_at = datetime.now(UTC)
                reviews.update_thread(current_review)
                return current_round
        except Exception as exc:
            self._mark_round_failed(review_id=review_id, round_id=round_id, error_message=str(exc))
            if isinstance(exc, ReviewRuntimeUnavailableError):
                raise
            raise

    def resolve_review(
        self,
        review_id: UUID,
        *,
        status: ReviewStatus,
        resolution_summary: str,
        resolved_by: str = "system",
    ) -> ReviewThread:
        if status == ReviewStatus.IN_REVIEW:
            msg = "reviews cannot be resolved to in_review"
            raise ValueError(msg)
        with session_scope(self._settings) as session:
            reviews = ReviewRepository(session)
            review = reviews.get_thread(review_id)
            if review is None:
                msg = f"review {review_id} not found"
                raise KeyError(msg)
            review.status = status
            review.resolution_summary = resolution_summary
            review.updated_at = datetime.now(UTC)
            reviews.update_thread(review)
            reviews.upsert_participant(
                ReviewParticipant(
                    review_id=review_id,
                    participant_key=resolved_by,
                    participant_type=ReviewParticipantType.SYSTEM,
                    role_label="resolution",
                )
            )
            reviews.create_post(
                ReviewPost(
                    review_id=review_id,
                    author_key=resolved_by,
                    author_type=ReviewParticipantType.SYSTEM,
                    body=resolution_summary,
                    structured_payload={"status": status.value},
                )
            )
            return review

    def _prepare_round_execution(
        self, review_id: UUID, round_id: UUID
    ) -> tuple[dict[str, Any], list[dict[str, Any]], ReviewRound, ReviewThread]:
        with session_scope(self._settings) as session:
            campaigns = CampaignRepository(session)
            runs = RunRepository(session)
            artifacts = ArtifactRepository(session)
            decisions = DecisionRepository(session)
            summaries = SummaryRepository(session)
            reviews = ReviewRepository(session)

            review = reviews.get_thread(review_id)
            round_record = reviews.get_round(round_id)
            if review is None or round_record is None or round_record.review_id != review_id:
                msg = "review or round not found"
                raise KeyError(msg)
            if review.status == ReviewStatus.RESOLVED:
                msg = f"review {review_id} is already resolved"
                raise ValueError(msg)
            campaign = campaigns.get(review.campaign_id)
            if campaign is None:
                msg = f"campaign {review.campaign_id} not found"
                raise KeyError(msg)
            run = runs.get_run(review.run_id) if review.run_id is not None else None
            artifact_links = reviews.list_artifact_links(review_id)
            linked_artifacts = artifacts.list_by_ids([link.artifact_id for link in artifact_links])
            prior_posts = [post.model_dump(mode="json") for post in reviews.list_posts(review_id)]
            context_bundle = {
                "review": review.model_dump(mode="json"),
                "campaign": campaign.model_dump(mode="json"),
                "run": run.model_dump(mode="json") if run is not None else None,
                "linked_artifacts": [
                    self._artifact_context_payload(artifact) for artifact in linked_artifacts
                ],
                "summaries": summaries.list_for_campaign(
                    review.campaign_id, run_id=review.run_id
                )[-5:],
                "decisions": [
                    decision.model_dump(mode="json")
                    for decision in decisions.list_for_campaign(
                        review.campaign_id, run_id=review.run_id
                    )[-10:]
                ],
            }
            round_record.status = ReviewRoundStatus.RUNNING
            round_record.started_at = round_record.started_at or datetime.now(UTC)
            reviews.update_round(round_record)
            context_artifact = self._artifact_store.write_text(
                review.campaign_id,
                review.run_id,
                ArtifactType.METADATA,
                f"reviews/{review.id}/rounds/{round_record.id}/context.json",
                ReviewAgentRequest(
                    agent_name="workflow_agent",
                    objective=review.objective,
                    context_bundle=context_bundle,
                    prior_posts=prior_posts,
                ).model_dump_json(indent=2),
            )
            context_artifact.metadata.update(
                {"review_id": str(review.id), "review_round_id": str(round_record.id)}
            )
            artifacts.create(context_artifact)
            return context_bundle, prior_posts, round_record, review

    def _mark_round_failed(self, *, review_id: UUID, round_id: UUID, error_message: str) -> None:
        with session_scope(self._settings) as session:
            reviews = ReviewRepository(session)
            round_record = reviews.get_round(round_id)
            review = reviews.get_thread(review_id)
            if round_record is None or review is None:
                return
            round_record.status = ReviewRoundStatus.FAILED
            round_record.error_message = error_message
            round_record.completed_at = datetime.now(UTC)
            reviews.update_round(round_record)
            review.status = ReviewStatus.OPEN
            review.updated_at = datetime.now(UTC)
            reviews.update_thread(review)
            reviews.upsert_participant(
                ReviewParticipant(
                    review_id=review_id,
                    participant_key="system",
                    participant_type=ReviewParticipantType.SYSTEM,
                    role_label="system",
                )
            )
            reviews.create_post(
                ReviewPost(
                    review_id=review_id,
                    round_id=round_id,
                    author_key="system",
                    author_type=ReviewParticipantType.SYSTEM,
                    body=f"Review round failed: {error_message}",
                    structured_payload={"error_message": error_message},
                )
            )

    def _artifact_context_payload(self, artifact: Any) -> dict[str, Any]:
        payload = artifact.model_dump(mode="json")
        path = Path(artifact.path)
        if self._should_inline_artifact(path=path, media_type=artifact.media_type):
            payload["inline_content"] = path.read_text(encoding="utf-8")
        return payload

    @staticmethod
    def _resolve_round_participants(
        mode: ReviewRoundMode, *, participant_keys: list[str] | None, run_attached: bool
    ) -> list[str]:
        if mode == ReviewRoundMode.SINGLE_PASS:
            return participant_keys or default_review_participants(run_attached)
        return normalize_moderated_participants(participant_keys, run_attached=run_attached)

    @staticmethod
    def _default_role_label(author_key: str, author_type: ReviewParticipantType) -> str:
        if author_type == ReviewParticipantType.HUMAN:
            return "researcher"
        if author_type == ReviewParticipantType.SYSTEM:
            return "system"
        return author_key

    @staticmethod
    def _should_inline_artifact(*, path: Path, media_type: str) -> bool:
        if not path.exists() or path.stat().st_size > _MAX_INLINE_ARTIFACT_BYTES:
            return False
        if media_type.startswith("text/") or media_type in _INLINE_TEXT_MEDIA_TYPES:
            return True
        return path.suffix.lower() in _INLINE_TEXT_SUFFIXES
