from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from autolab.core.enums import (
    ArtifactType,
    CampaignMode,
    CampaignStatus,
    ConstraintOperator,
    FailureClass,
    ObjectiveDirection,
    ParameterKind,
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
    Constraint,
    Objective,
    OptimizerState,
    ReviewArtifactLink,
    ReviewParticipant,
    ReviewPost,
    ReviewRound,
    ReviewThread,
    ReviewThreadDetail,
    SearchSpace,
    SearchSpaceDimension,
    SimulationExecutionRecord,
    SimulationRun,
    SimulationWorkflow,
)
from autolab.storage.models import (
    AgentDecisionORM,
    ArtifactORM,
    CampaignORM,
    CandidateORM,
    ConfigSnapshotORM,
    ConstraintORM,
    ObjectiveORM,
    OptimizerStateORM,
    ReviewArtifactLinkORM,
    ReviewParticipantORM,
    ReviewPostORM,
    ReviewRoundORM,
    ReviewThreadORM,
    RunMetricORM,
    SearchDimensionORM,
    SimulationRunORM,
    SimulatorProvenanceORM,
    StageExecutionORM,
    SummaryORM,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


class CampaignRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, campaign: Campaign) -> Campaign:
        campaign_row = CampaignORM(
            id=str(campaign.id),
            name=campaign.name,
            description=campaign.description,
            mode=campaign.mode.value,
            simulator=campaign.simulator.value,
            status=campaign.status.value,
            seed=campaign.seed,
            budget_max_runs=campaign.budget.max_runs,
            budget_batch_size=campaign.budget.batch_size,
            budget_max_failures=campaign.budget.max_failures,
            tags=campaign.tags,
            workflow_payload=(
                campaign.workflow.model_dump(mode="json") if campaign.workflow is not None else None
            ),
            metadata_payload=campaign.metadata,
        )
        campaign_row.objectives = [
            ObjectiveORM(
                name=objective.name,
                metric_key=objective.metric_key,
                direction=objective.direction.value,
                weight=objective.weight,
            )
            for objective in campaign.objectives
        ]
        campaign_row.constraints = [
            ConstraintORM(
                name=constraint.name,
                metric_key=constraint.metric_key,
                operator=constraint.operator.value,
                threshold=constraint.threshold,
            )
            for constraint in campaign.constraints
        ]
        campaign_row.search_dimensions = [
            SearchDimensionORM(
                name=dimension.name,
                kind=dimension.kind.value,
                lower=float(dimension.lower) if dimension.lower is not None else None,
                upper=float(dimension.upper) if dimension.upper is not None else None,
                choices=dimension.choices,
            )
            for dimension in campaign.search_space.dimensions
        ]
        self._session.add(campaign_row)
        self._session.flush()
        return campaign

    def get(self, campaign_id: UUID) -> Campaign | None:
        row = self._session.get(CampaignORM, str(campaign_id))
        if row is None:
            return None
        return self._to_domain(row)

    def list(self) -> list[Campaign]:
        rows = self._session.scalars(select(CampaignORM).order_by(CampaignORM.created_at.desc())).all()
        return [self._to_domain(row) for row in rows]

    def update_status(self, campaign_id: UUID, status: CampaignStatus) -> Campaign:
        row = self._session.get(CampaignORM, str(campaign_id))
        if row is None:
            msg = f"campaign {campaign_id} not found"
            raise KeyError(msg)
        row.status = status.value
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return self._to_domain(row)

    def save_config_snapshot(
        self, campaign_id: UUID, sha256: str, payload: dict[str, object]
    ) -> None:
        self._session.add(
            ConfigSnapshotORM(campaign_id=str(campaign_id), sha256=sha256, payload=payload)
        )

    def save_summary(
        self, campaign_id: UUID, summary_type: str, body: str, run_id: UUID | None
    ) -> None:
        self._session.add(
            SummaryORM(
                campaign_id=str(campaign_id),
                run_id=str(run_id) if run_id is not None else None,
                summary_type=summary_type,
                body=body,
            )
        )

    def _to_domain(self, row: CampaignORM) -> Campaign:
        return Campaign(
            id=UUID(row.id),
            name=row.name,
            description=row.description,
            mode=CampaignMode(row.mode),
            objectives=[
                Objective(
                    name=objective.name,
                    metric_key=objective.metric_key,
                    direction=ObjectiveDirection(objective.direction),
                    weight=objective.weight,
                )
                for objective in row.objectives
            ],
            constraints=[
                Constraint(
                    name=constraint.name,
                    metric_key=constraint.metric_key,
                    operator=ConstraintOperator(constraint.operator),
                    threshold=constraint.threshold,
                )
                for constraint in row.constraints
            ],
            search_space=SearchSpace(
                dimensions=[
                    SearchSpaceDimension(
                        name=dimension.name,
                        kind=ParameterKind(dimension.kind),
                        lower=dimension.lower,
                        upper=dimension.upper,
                        choices=dimension.choices,
                    )
                    for dimension in row.search_dimensions
                ]
            ),
            budget=CampaignBudget(
                max_runs=row.budget_max_runs,
                batch_size=row.budget_batch_size,
                max_failures=row.budget_max_failures,
            ),
            simulator=SimulatorKind(row.simulator),
            workflow=(
                SimulationWorkflow.model_validate(row.workflow_payload)
                if row.workflow_payload is not None
                else None
            ),
            status=CampaignStatus(row.status),
            seed=row.seed,
            tags=row.tags,
            metadata=row.metadata_payload,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class RunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_candidate(self, candidate: Candidate) -> Candidate:
        self._session.add(
            CandidateORM(
                id=str(candidate.id),
                campaign_id=str(candidate.campaign_id),
                batch_index=candidate.batch_index,
                source=candidate.source,
                values_payload=candidate.values,
                predicted_metrics=candidate.predicted_metrics,
                metadata_payload=candidate.metadata,
            )
        )
        self._session.flush()
        return candidate

    def create_run(self, run: SimulationRun) -> SimulationRun:
        row = SimulationRunORM(
            id=str(run.id),
            campaign_id=str(run.campaign_id),
            candidate_id=str(run.candidate_id),
            simulator=run.simulator.value,
            status=run.status.value,
            failure_class=run.failure_class.value,
            job_id=run.job_id,
            attempt=run.attempt,
            metadata_payload=run.metadata,
        )
        row.metrics = [RunMetricORM(name=name, value=value) for name, value in run.metrics.items()]
        self._session.add(row)
        self._session.flush()
        return run

    def update_run(self, run: SimulationRun) -> SimulationRun:
        row = self._session.get(SimulationRunORM, str(run.id))
        if row is None:
            msg = f"run {run.id} not found"
            raise KeyError(msg)
        row.status = run.status.value
        row.failure_class = run.failure_class.value
        row.job_id = run.job_id
        row.attempt = run.attempt
        row.metadata_payload = run.metadata
        row.updated_at = datetime.now(UTC)
        row.metrics.clear()
        row.metrics.extend(
            RunMetricORM(name=name, value=value) for name, value in run.metrics.items()
        )
        self._session.flush()
        return run

    def list_runs(self, campaign_id: UUID) -> list[SimulationRun]:
        rows = self._session.scalars(
            select(SimulationRunORM).where(SimulationRunORM.campaign_id == str(campaign_id))
        ).all()
        return [self._to_domain(row) for row in rows]

    def get_run(self, run_id: UUID) -> SimulationRun | None:
        row = self._session.get(SimulationRunORM, str(run_id))
        return None if row is None else self._to_domain(row)

    def list_candidates(self, campaign_id: UUID) -> list[Candidate]:
        rows = self._session.scalars(
            select(CandidateORM).where(CandidateORM.campaign_id == str(campaign_id))
        ).all()
        return [
            Candidate(
                id=UUID(row.id),
                campaign_id=UUID(row.campaign_id),
                values=row.values_payload,
                batch_index=row.batch_index,
                source=row.source,
                predicted_metrics=row.predicted_metrics,
                metadata=row.metadata_payload,
            )
            for row in rows
        ]

    def _to_domain(self, row: SimulationRunORM) -> SimulationRun:
        return SimulationRun(
            id=UUID(row.id),
            campaign_id=UUID(row.campaign_id),
            candidate_id=UUID(row.candidate_id),
            simulator=SimulatorKind(row.simulator),
            status=RunStatus(row.status),
            failure_class=FailureClass(row.failure_class),
            job_id=row.job_id,
            attempt=row.attempt,
            metrics={metric.name: metric.value for metric in row.metrics},
            metadata=row.metadata_payload,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class ArtifactRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, artifact: ArtifactRecord) -> ArtifactRecord:
        self._session.add(
            ArtifactORM(
                id=str(artifact.id),
                campaign_id=str(artifact.campaign_id),
                run_id=str(artifact.run_id) if artifact.run_id is not None else None,
                artifact_type=artifact.artifact_type.value,
                path=artifact.path,
                media_type=artifact.media_type,
                sha256=artifact.sha256,
                metadata_payload=artifact.metadata,
            )
        )
        self._session.flush()
        return artifact

    def get(self, artifact_id: UUID) -> ArtifactRecord | None:
        row = self._session.get(ArtifactORM, str(artifact_id))
        if row is None:
            return None
        return ArtifactRecord(
            id=UUID(row.id),
            campaign_id=UUID(row.campaign_id),
            run_id=UUID(row.run_id) if row.run_id else None,
            artifact_type=ArtifactType(row.artifact_type),
            path=row.path,
            media_type=row.media_type,
            sha256=row.sha256,
            metadata=row.metadata_payload,
            created_at=row.created_at,
        )

    def list_by_ids(self, artifact_ids: list[UUID]) -> list[ArtifactRecord]:
        if not artifact_ids:
            return []
        rows = self._session.scalars(
            select(ArtifactORM).where(
                ArtifactORM.id.in_([str(artifact_id) for artifact_id in artifact_ids])
            )
        ).all()
        return [
            ArtifactRecord(
                id=UUID(row.id),
                campaign_id=UUID(row.campaign_id),
                run_id=UUID(row.run_id) if row.run_id else None,
                artifact_type=ArtifactType(row.artifact_type),
                path=row.path,
                media_type=row.media_type,
                sha256=row.sha256,
                metadata=row.metadata_payload,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def list_for_campaign(self, campaign_id: UUID) -> list[ArtifactRecord]:
        rows = self._session.scalars(
            select(ArtifactORM)
            .where(ArtifactORM.campaign_id == str(campaign_id))
            .order_by(ArtifactORM.created_at)
        ).all()
        return [
            ArtifactRecord(
                id=UUID(row.id),
                campaign_id=UUID(row.campaign_id),
                run_id=UUID(row.run_id) if row.run_id else None,
                artifact_type=ArtifactType(row.artifact_type),
                path=row.path,
                media_type=row.media_type,
                sha256=row.sha256,
                metadata=row.metadata_payload,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def list_for_run(self, run_id: UUID, stage_name: str | None = None) -> list[ArtifactRecord]:
        rows = self._session.scalars(
            select(ArtifactORM)
            .where(ArtifactORM.run_id == str(run_id))
            .order_by(ArtifactORM.created_at)
        ).all()
        records = [
            ArtifactRecord(
                id=UUID(row.id),
                campaign_id=UUID(row.campaign_id),
                run_id=UUID(row.run_id) if row.run_id else None,
                artifact_type=ArtifactType(row.artifact_type),
                path=row.path,
                media_type=row.media_type,
                sha256=row.sha256,
                metadata=row.metadata_payload,
                created_at=row.created_at,
            )
            for row in rows
        ]
        if stage_name is None:
            return records
        return [record for record in records if record.metadata.get("stage_name") == stage_name]


class StageExecutionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: SimulationExecutionRecord) -> SimulationExecutionRecord:
        self._session.add(
            StageExecutionORM(
                id=str(record.id),
                experiment_id=str(record.experiment_id),
                campaign_id=str(record.campaign_id),
                candidate_id=str(record.candidate_id),
                simulator=record.simulator.value,
                stage_name=record.stage_name,
                workdir_path=record.workdir_path,
                command=record.command,
                environment=record.environment,
                input_files=record.input_files,
                output_files=record.output_files,
                log_files=record.log_files,
                status=record.status.value,
                exit_code=record.exit_code,
                message=record.message,
                simulator_version=record.simulator_version,
                started_at=record.started_at,
                ended_at=record.ended_at,
                metadata_payload=record.metadata,
            )
        )
        self._session.flush()
        return record

    def update(self, record: SimulationExecutionRecord) -> SimulationExecutionRecord:
        row = self._session.get(StageExecutionORM, str(record.id))
        if row is None:
            msg = f"stage execution {record.id} not found"
            raise KeyError(msg)
        row.command = record.command
        row.environment = record.environment
        row.input_files = record.input_files
        row.output_files = record.output_files
        row.log_files = record.log_files
        row.status = record.status.value
        row.exit_code = record.exit_code
        row.message = record.message
        row.simulator_version = record.simulator_version
        row.started_at = record.started_at
        row.ended_at = record.ended_at
        row.metadata_payload = record.metadata
        self._session.flush()
        return record

    def list_for_campaign(self, campaign_id: UUID) -> list[SimulationExecutionRecord]:
        rows = self._session.scalars(
            select(StageExecutionORM).where(StageExecutionORM.campaign_id == str(campaign_id))
        ).all()
        return [self._to_domain(row) for row in rows]

    def list_for_experiment(self, experiment_id: UUID) -> list[SimulationExecutionRecord]:
        rows = self._session.scalars(
            select(StageExecutionORM).where(StageExecutionORM.experiment_id == str(experiment_id))
        ).all()
        return [self._to_domain(row) for row in rows]

    def _to_domain(self, row: StageExecutionORM) -> SimulationExecutionRecord:
        return SimulationExecutionRecord(
            id=UUID(row.id),
            experiment_id=UUID(row.experiment_id),
            campaign_id=UUID(row.campaign_id),
            candidate_id=UUID(row.candidate_id),
            simulator=SimulatorKind(row.simulator),
            stage_name=row.stage_name,
            workdir_path=row.workdir_path,
            command=row.command,
            environment=row.environment,
            input_files=row.input_files,
            output_files=row.output_files,
            log_files=row.log_files,
            status=RunStatus(row.status),
            exit_code=row.exit_code,
            message=row.message,
            simulator_version=row.simulator_version,
            started_at=row.started_at,
            ended_at=row.ended_at,
            metadata=row.metadata_payload,
        )


class SimulatorProvenanceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        run_id: UUID,
        simulator: SimulatorKind,
        adapter_version: str,
        input_sha256: str,
        output_sha256: str | None,
        payload: dict[str, object],
    ) -> None:
        self._session.add(
            SimulatorProvenanceORM(
                run_id=str(run_id),
                simulator=simulator.value,
                adapter_version=adapter_version,
                input_sha256=input_sha256,
                output_sha256=output_sha256,
                payload=payload,
            )
        )


class DecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, decision: AgentDecision) -> AgentDecision:
        self._session.add(
            AgentDecisionORM(
                id=str(decision.id),
                campaign_id=str(decision.campaign_id),
                run_id=str(decision.run_id) if decision.run_id is not None else None,
                agent_name=decision.agent_name,
                action=decision.action,
                rationale=decision.rationale,
                structured_output=decision.structured_output,
            )
        )
        self._session.flush()
        return decision

    def list_for_campaign(
        self, campaign_id: UUID, run_id: UUID | None = None
    ) -> list[AgentDecision]:
        statement = select(AgentDecisionORM).where(AgentDecisionORM.campaign_id == str(campaign_id))
        if run_id is not None:
            statement = statement.where(AgentDecisionORM.run_id == str(run_id))
        rows = self._session.scalars(statement.order_by(AgentDecisionORM.created_at)).all()
        return [
            AgentDecision(
                id=UUID(row.id),
                campaign_id=UUID(row.campaign_id),
                run_id=UUID(row.run_id) if row.run_id is not None else None,
                agent_name=row.agent_name,
                action=row.action,
                rationale=row.rationale,
                structured_output=row.structured_output,
                created_at=row.created_at,
            )
            for row in rows
        ]


class SummaryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_campaign(
        self, campaign_id: UUID, run_id: UUID | None = None
    ) -> list[dict[str, object]]:
        statement = select(SummaryORM).where(SummaryORM.campaign_id == str(campaign_id))
        if run_id is not None:
            statement = statement.where(SummaryORM.run_id == str(run_id))
        rows = self._session.scalars(statement.order_by(SummaryORM.created_at)).all()
        return [
            {
                "id": row.id,
                "campaign_id": row.campaign_id,
                "run_id": row.run_id,
                "summary_type": row.summary_type,
                "body": row.body,
                "created_at": row.created_at,
            }
            for row in rows
        ]


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_thread(self, review: ReviewThread) -> ReviewThread:
        self._session.add(
            ReviewThreadORM(
                id=str(review.id),
                campaign_id=str(review.campaign_id),
                run_id=str(review.run_id) if review.run_id is not None else None,
                title=review.title,
                objective=review.objective,
                status=review.status.value,
                created_by=review.created_by,
                resolution_summary=review.resolution_summary,
                created_at=review.created_at,
                updated_at=review.updated_at,
            )
        )
        self._session.flush()
        return review

    def get_thread(self, review_id: UUID) -> ReviewThread | None:
        row = self._session.get(ReviewThreadORM, str(review_id))
        return None if row is None else self._thread_to_domain(row)

    def get_thread_detail(self, review_id: UUID) -> ReviewThreadDetail | None:
        thread = self.get_thread(review_id)
        if thread is None:
            return None
        return ReviewThreadDetail(
            **thread.model_dump(),
            participants=self.list_participants(review_id),
            artifact_ids=[link.artifact_id for link in self.list_artifact_links(review_id)],
            rounds=self.list_rounds(review_id),
        )

    def list_threads(self, campaign_id: UUID, run_id: UUID | None = None) -> list[ReviewThread]:
        statement = select(ReviewThreadORM).where(ReviewThreadORM.campaign_id == str(campaign_id))
        if run_id is not None:
            statement = statement.where(ReviewThreadORM.run_id == str(run_id))
        rows = self._session.scalars(statement.order_by(ReviewThreadORM.created_at.desc())).all()
        return [self._thread_to_domain(row) for row in rows]

    def update_thread(self, review: ReviewThread) -> ReviewThread:
        row = self._session.get(ReviewThreadORM, str(review.id))
        if row is None:
            msg = f"review {review.id} not found"
            raise KeyError(msg)
        row.title = review.title
        row.objective = review.objective
        row.status = review.status.value
        row.created_by = review.created_by
        row.resolution_summary = review.resolution_summary
        row.updated_at = review.updated_at
        self._session.flush()
        return review

    def upsert_participant(self, participant: ReviewParticipant) -> ReviewParticipant:
        statement = select(ReviewParticipantORM).where(
            ReviewParticipantORM.review_id == str(participant.review_id),
            ReviewParticipantORM.participant_key == participant.participant_key,
        )
        row = self._session.scalar(statement)
        if row is None:
            row = ReviewParticipantORM(
                id=str(participant.id),
                review_id=str(participant.review_id),
                participant_key=participant.participant_key,
                participant_type=participant.participant_type.value,
                role_label=participant.role_label,
                created_at=participant.created_at,
            )
            self._session.add(row)
        else:
            row.participant_type = participant.participant_type.value
            row.role_label = participant.role_label
        self._session.flush()
        return participant

    def list_participants(self, review_id: UUID) -> list[ReviewParticipant]:
        rows = self._session.scalars(
            select(ReviewParticipantORM)
            .where(ReviewParticipantORM.review_id == str(review_id))
            .order_by(ReviewParticipantORM.created_at)
        ).all()
        return [
            ReviewParticipant(
                id=UUID(row.id),
                review_id=UUID(row.review_id),
                participant_key=row.participant_key,
                participant_type=ReviewParticipantType(row.participant_type),
                role_label=row.role_label,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def create_post(self, post: ReviewPost) -> ReviewPost:
        self._session.add(
            ReviewPostORM(
                id=str(post.id),
                review_id=str(post.review_id),
                round_id=str(post.round_id) if post.round_id is not None else None,
                parent_post_id=(
                    str(post.parent_post_id) if post.parent_post_id is not None else None
                ),
                author_key=post.author_key,
                author_type=post.author_type.value,
                body=post.body,
                structured_payload=post.structured_payload,
                created_at=post.created_at,
            )
        )
        self._session.flush()
        return post

    def list_posts(self, review_id: UUID) -> list[ReviewPost]:
        rows = self._session.scalars(
            select(ReviewPostORM)
            .where(ReviewPostORM.review_id == str(review_id))
            .order_by(ReviewPostORM.created_at)
        ).all()
        return [
            ReviewPost(
                id=UUID(row.id),
                review_id=UUID(row.review_id),
                round_id=UUID(row.round_id) if row.round_id is not None else None,
                parent_post_id=UUID(row.parent_post_id) if row.parent_post_id is not None else None,
                author_key=row.author_key,
                author_type=ReviewParticipantType(row.author_type),
                body=row.body,
                structured_payload=row.structured_payload,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def create_round(self, round_record: ReviewRound) -> ReviewRound:
        self._session.add(
            ReviewRoundORM(
                id=str(round_record.id),
                review_id=str(round_record.review_id),
                mode=round_record.mode.value,
                status=round_record.status.value,
                participant_keys=round_record.participant_keys,
                recommendation=(
                    round_record.recommendation.value
                    if round_record.recommendation is not None
                    else None
                ),
                error_message=round_record.error_message,
                metadata_payload=round_record.metadata,
                created_at=round_record.created_at,
                started_at=round_record.started_at,
                completed_at=round_record.completed_at,
            )
        )
        self._session.flush()
        return round_record

    def get_round(self, round_id: UUID) -> ReviewRound | None:
        row = self._session.get(ReviewRoundORM, str(round_id))
        return None if row is None else self._round_to_domain(row)

    def list_rounds(self, review_id: UUID) -> list[ReviewRound]:
        rows = self._session.scalars(
            select(ReviewRoundORM)
            .where(ReviewRoundORM.review_id == str(review_id))
            .order_by(ReviewRoundORM.created_at)
        ).all()
        return [self._round_to_domain(row) for row in rows]

    def update_round(self, round_record: ReviewRound) -> ReviewRound:
        row = self._session.get(ReviewRoundORM, str(round_record.id))
        if row is None:
            msg = f"review round {round_record.id} not found"
            raise KeyError(msg)
        row.mode = round_record.mode.value
        row.status = round_record.status.value
        row.participant_keys = round_record.participant_keys
        row.recommendation = (
            round_record.recommendation.value if round_record.recommendation is not None else None
        )
        row.error_message = round_record.error_message
        row.metadata_payload = round_record.metadata
        row.started_at = round_record.started_at
        row.completed_at = round_record.completed_at
        self._session.flush()
        return round_record

    def create_artifact_link(self, link: ReviewArtifactLink) -> ReviewArtifactLink:
        self._session.add(
            ReviewArtifactLinkORM(
                id=str(link.id),
                review_id=str(link.review_id),
                artifact_id=str(link.artifact_id),
                created_at=link.created_at,
            )
        )
        self._session.flush()
        return link

    def list_artifact_links(self, review_id: UUID) -> list[ReviewArtifactLink]:
        rows = self._session.scalars(
            select(ReviewArtifactLinkORM)
            .where(ReviewArtifactLinkORM.review_id == str(review_id))
            .order_by(ReviewArtifactLinkORM.created_at)
        ).all()
        return [
            ReviewArtifactLink(
                id=UUID(row.id),
                review_id=UUID(row.review_id),
                artifact_id=UUID(row.artifact_id),
                created_at=row.created_at,
            )
            for row in rows
        ]

    @staticmethod
    def _thread_to_domain(row: ReviewThreadORM) -> ReviewThread:
        return ReviewThread(
            id=UUID(row.id),
            campaign_id=UUID(row.campaign_id),
            run_id=UUID(row.run_id) if row.run_id is not None else None,
            title=row.title,
            objective=row.objective,
            status=ReviewStatus(row.status),
            created_by=row.created_by,
            resolution_summary=row.resolution_summary,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _round_to_domain(row: ReviewRoundORM) -> ReviewRound:
        return ReviewRound(
            id=UUID(row.id),
            review_id=UUID(row.review_id),
            mode=ReviewRoundMode(row.mode),
            status=ReviewRoundStatus(row.status),
            participant_keys=row.participant_keys,
            recommendation=ReviewStatus(row.recommendation) if row.recommendation else None,
            error_message=row.error_message,
            metadata=row.metadata_payload,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )


class OptimizerStateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, campaign_id: UUID) -> OptimizerState | None:
        row = self._session.get(OptimizerStateORM, str(campaign_id))
        if row is None:
            return None
        return OptimizerState(
            campaign_id=campaign_id,
            algorithm=row.algorithm,
            observation_count=row.observation_count,
            payload=row.payload,
            updated_at=row.updated_at,
        )

    def upsert(self, state: OptimizerState) -> OptimizerState:
        row = self._session.get(OptimizerStateORM, str(state.campaign_id))
        if row is None:
            row = OptimizerStateORM(
                campaign_id=str(state.campaign_id),
                algorithm=state.algorithm,
                observation_count=state.observation_count,
                payload=state.payload,
            )
            self._session.add(row)
        else:
            row.algorithm = state.algorithm
            row.observation_count = state.observation_count
            row.payload = state.payload
            row.updated_at = state.updated_at
        self._session.flush()
        return state
