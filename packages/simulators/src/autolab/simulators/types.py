from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from autolab.core.enums import RunStatus, SimulatorKind
from autolab.core.models import AutolabModel, SimulationInput, ValidationReport
from pydantic import Field


class PreparedRun(AutolabModel):
    id: UUID = Field(default_factory=uuid4)
    campaign_id: UUID
    candidate_id: UUID
    simulator: SimulatorKind
    simulation_input: SimulationInput
    command: list[str] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobHandle(AutolabModel):
    id: str
    prepared_run_id: UUID
    simulator: SimulatorKind
    status: RunStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationStatus(AutolabModel):
    job_id: str
    status: RunStatus
    terminal: bool
    message: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ValidationOutcome(AutolabModel):
    report: ValidationReport
    metadata: dict[str, Any] = Field(default_factory=dict)
