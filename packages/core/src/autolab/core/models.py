from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

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
