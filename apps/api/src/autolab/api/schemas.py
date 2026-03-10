from __future__ import annotations

from typing import Any
from uuid import UUID

from autolab.core.enums import CampaignMode, CampaignStatus, SimulatorKind
from autolab.core.models import (
    CampaignBudget,
    Constraint,
    Objective,
    SearchSpace,
    SimulationRun,
)
from pydantic import BaseModel, Field


class CreateCampaignRequest(BaseModel):
    name: str
    description: str = ""
    mode: CampaignMode
    objectives: list[Objective]
    constraints: list[Constraint] = Field(default_factory=list)
    search_space: SearchSpace
    budget: CampaignBudget
    simulator: SimulatorKind = SimulatorKind.FAKE
    seed: int = 42
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CampaignResponse(BaseModel):
    id: UUID
    name: str
    status: CampaignStatus
    simulator: SimulatorKind
    mode: CampaignMode
    budget: CampaignBudget
    tags: list[str]


class StepCampaignRequest(BaseModel):
    execute_inline: bool = False


class StepCampaignResponse(BaseModel):
    campaign_id: UUID
    status: str
    run_ids: list[UUID] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    services: dict[str, str]


class RunListResponse(BaseModel):
    runs: list[SimulationRun]
