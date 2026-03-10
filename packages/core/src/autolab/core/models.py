from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

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
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AutolabModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, use_enum_values=False)


class Objective(AutolabModel):
    name: str
    metric_key: str
    direction: ObjectiveDirection
    weight: float = 1.0


class Constraint(AutolabModel):
    name: str
    metric_key: str
    operator: ConstraintOperator
    threshold: float


class SearchSpaceDimension(AutolabModel):
    name: str
    kind: ParameterKind
    lower: float | int | None = None
    upper: float | int | None = None
    choices: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shape(self) -> SearchSpaceDimension:
        if self.kind == ParameterKind.CATEGORICAL:
            if not self.choices:
                msg = "categorical dimensions require at least one choice"
                raise ValueError(msg)
            return self
        if self.lower is None or self.upper is None:
            msg = "numeric dimensions require lower and upper bounds"
            raise ValueError(msg)
        if self.lower >= self.upper:
            msg = "lower bound must be smaller than upper bound"
            raise ValueError(msg)
        return self


class SearchSpace(AutolabModel):
    dimensions: list[SearchSpaceDimension]

    def dimension_names(self) -> list[str]:
        return [dimension.name for dimension in self.dimensions]


class MaterialCandidate(AutolabModel):
    name: str = ""
    formula: str = ""
    composition: dict[str, float | int | str] = Field(default_factory=dict)
    properties: dict[str, float | int | str | bool] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeometrySpec(AutolabModel):
    kind: str = "generic"
    parameters: dict[str, Any] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BoundaryConditionSpec(AutolabModel):
    name: str
    kind: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MeshSpec(AutolabModel):
    strategy: str = "auto"
    resolution: float | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationTask(AutolabModel):
    name: str
    simulator: SimulatorKind
    parameters: dict[str, Any] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    material: MaterialCandidate | None = None
    geometry: GeometrySpec | None = None
    boundary_conditions: list[BoundaryConditionSpec] = Field(default_factory=list)
    mesh: MeshSpec | None = None
    expected_outputs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationStage(AutolabModel):
    name: str
    simulator: SimulatorKind
    task: SimulationTask
    depends_on: list[str] = Field(default_factory=list)
    mapping_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationWorkflow(AutolabModel):
    name: str = "default"
    stages: list[SimulationStage]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("stages")
    @classmethod
    def ensure_stages(cls, value: list[SimulationStage]) -> list[SimulationStage]:
        if not value:
            msg = "at least one stage is required"
            raise ValueError(msg)
        names = [stage.name for stage in value]
        if len(names) != len(set(names)):
            msg = "stage names must be unique"
            raise ValueError(msg)
        available = set(names)
        for stage in value:
            missing = [dependency for dependency in stage.depends_on if dependency not in available]
            if missing:
                msg = f"stage {stage.name} depends on unknown stages: {', '.join(missing)}"
                raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_acyclic(self) -> SimulationWorkflow:
        graph = {stage.name: tuple(stage.depends_on) for stage in self.stages}
        visiting: set[str] = set()
        visited: set[str] = set()

        def _visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                msg = f"workflow {self.name} contains a cycle at stage {node}"
                raise ValueError(msg)
            visiting.add(node)
            for dependency in graph[node]:
                _visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for name in graph:
            _visit(name)
        return self

    def stage_map(self) -> dict[str, SimulationStage]:
        return {stage.name: stage for stage in self.stages}

    def ordered_stages(self) -> list[SimulationStage]:
        ordered: list[SimulationStage] = []
        seen: set[str] = set()
        stages = self.stage_map()

        def _add(stage_name: str) -> None:
            if stage_name in seen:
                return
            for dependency in stages[stage_name].depends_on:
                _add(dependency)
            seen.add(stage_name)
            ordered.append(stages[stage_name])

        for stage in self.stages:
            _add(stage.name)
        return ordered


class SimulationArtifact(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    artifact_type: ArtifactType
    artifact_role: str
    path: str
    media_type: str = "application/octet-stream"
    sha256: str | None = None
    stage_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SimulationExecutionRecord(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    experiment_id: UUID
    campaign_id: UUID
    candidate_id: UUID
    simulator: SimulatorKind
    stage_name: str
    workdir_path: str
    command: list[str] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    input_files: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)
    log_files: list[str] = Field(default_factory=list)
    status: RunStatus = RunStatus.PENDING
    exit_code: int | None = None
    message: str = ""
    simulator_version: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationParseResult(AutolabModel):
    experiment_id: UUID
    campaign_id: UUID
    candidate_id: UUID
    simulator: SimulatorKind
    stage_name: str
    status: RunStatus
    scalar_metrics: dict[str, float] = Field(default_factory=dict)
    timeseries: dict[str, list[float]] = Field(default_factory=dict)
    convergence: bool | None = None
    warnings: list[str] = Field(default_factory=list)
    parse_errors: list[str] = Field(default_factory=list)
    raw_output_references: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationValidationResult(AutolabModel):
    experiment_id: UUID
    campaign_id: UUID
    candidate_id: UUID
    simulator: SimulatorKind
    stage_name: str
    status: Literal["valid", "invalid", "partial"] = "valid"
    reasons: list[str] = Field(default_factory=list)
    failure_class: FailureClass = FailureClass.NONE
    retryable: bool = False
    derived_metrics: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return self.status == "valid"


class ExperimentSpec(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    campaign_id: UUID
    candidate_id: UUID
    simulator: SimulatorKind
    simulator_version: str | None = None
    stage_name: str
    workflow_name: str = "default"
    parameters: dict[str, Any] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    workdir_path: str = ""
    material: MaterialCandidate | None = None
    geometry: GeometrySpec | None = None
    boundary_conditions: list[BoundaryConditionSpec] = Field(default_factory=list)
    mesh: MeshSpec | None = None
    workflow: SimulationWorkflow | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CampaignBudget(AutolabModel):
    max_runs: int = Field(ge=1)
    batch_size: int = Field(default=1, ge=1)
    max_failures: int = Field(default=3, ge=1)


class Campaign(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    mode: CampaignMode
    objectives: list[Objective]
    constraints: list[Constraint] = Field(default_factory=list)
    search_space: SearchSpace
    budget: CampaignBudget
    simulator: SimulatorKind
    workflow: SimulationWorkflow | None = None
    status: CampaignStatus = CampaignStatus.DRAFT
    seed: int = 42
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("objectives")
    @classmethod
    def ensure_objectives(cls, value: list[Objective]) -> list[Objective]:
        if not value:
            msg = "at least one objective is required"
            raise ValueError(msg)
        return value


class Candidate(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    campaign_id: UUID
    values: dict[str, float | int | str]
    batch_index: int = 0
    source: str = "optimizer"
    predicted_metrics: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationInput(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    campaign_id: UUID
    candidate_id: UUID
    simulator: SimulatorKind
    experiment_id: UUID | None = None
    stage_name: str | None = None
    payload: dict[str, Any]
    seed: int
    working_directory: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SimulationRun(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    campaign_id: UUID
    candidate_id: UUID
    simulator: SimulatorKind
    status: RunStatus = RunStatus.PENDING
    failure_class: FailureClass = FailureClass.NONE
    job_id: str | None = None
    attempt: int = 0
    metrics: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SimulationResult(AutolabModel):
    run_id: UUID
    candidate_id: UUID
    simulator: SimulatorKind
    status: RunStatus
    metrics: dict[str, float]
    raw_outputs: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    artifact_paths: list[str] = Field(default_factory=list)
    failure_class: FailureClass = FailureClass.NONE
    execution: SimulationExecutionRecord | None = None
    parsed: SimulationParseResult | None = None
    validation: SimulationValidationResult | None = None


class ValidationIssue(AutolabModel):
    code: str
    message: str
    level: str = "error"


class ValidationReport(AutolabModel):
    run_id: UUID | None = None
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    derived_metrics: dict[str, float] = Field(default_factory=dict)


class OptimizerState(AutolabModel):
    campaign_id: UUID
    algorithm: str
    observation_count: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentDecision(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    campaign_id: UUID
    run_id: UUID | None = None
    agent_name: str
    action: str
    rationale: str
    structured_output: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ArtifactRecord(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    campaign_id: UUID
    run_id: UUID | None = None
    artifact_type: ArtifactType
    path: str
    media_type: str = "application/json"
    sha256: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewParticipant(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    review_id: UUID
    participant_key: str
    participant_type: ReviewParticipantType
    role_label: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewPost(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    review_id: UUID
    round_id: UUID | None = None
    parent_post_id: UUID | None = None
    author_key: str
    author_type: ReviewParticipantType
    body: str
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewRound(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    review_id: UUID
    mode: ReviewRoundMode = ReviewRoundMode.MODERATED_PANEL
    status: ReviewRoundStatus = ReviewRoundStatus.QUEUED
    participant_keys: list[str] = Field(default_factory=list)
    recommendation: ReviewStatus | None = None
    error_message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ReviewArtifactLink(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    review_id: UUID
    artifact_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewThread(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    campaign_id: UUID
    run_id: UUID | None = None
    title: str
    objective: str
    status: ReviewStatus = ReviewStatus.OPEN
    created_by: str
    resolution_summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewThreadDetail(ReviewThread):
    participants: list[ReviewParticipant] = Field(default_factory=list)
    artifact_ids: list[UUID] = Field(default_factory=list)
    rounds: list[ReviewRound] = Field(default_factory=list)
