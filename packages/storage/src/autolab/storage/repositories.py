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
    SearchSpace,
    SearchSpaceDimension,
    SimulationRun,
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
    RunMetricORM,
    SearchDimensionORM,
    SimulationRunORM,
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
