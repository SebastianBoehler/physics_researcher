from __future__ import annotations

from typing import Any
from uuid import UUID

from autolab.agents import (
    LiteraturePaperInput,
    LiteratureResearchResult,
    PeptideBenchmarkExpectation,
    PeptideResearchResult,
)
from autolab.core.enums import (
    CampaignMode,
    CampaignStatus,
    ResearchMode,
    ReviewParticipantType,
    ReviewRoundMode,
    ReviewStatus,
    SimulatorKind,
)
from autolab.core.models import (
    ArtifactRecord,
    CampaignBudget,
    Constraint,
    Objective,
    ReviewPost,
    ReviewRound,
    ReviewThread,
    ReviewThreadDetail,
    SearchSpace,
    SimulationRun,
    SimulationWorkflow,
)
from autolab.skills import SkillMetadata
from pydantic import BaseModel, Field


class CreateCampaignRequest(BaseModel):
    name: str
    description: str = ""
    mode: CampaignMode
    objectives: list[Objective]
    constraints: list[Constraint] = Field(default_factory=list)
    search_space: SearchSpace
    budget: CampaignBudget
    simulator: SimulatorKind = SimulatorKind.LAMMPS
    workflow: SimulationWorkflow | None = None
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


class CampaignListResponse(BaseModel):
    campaigns: list[CampaignResponse]


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


class ArtifactListResponse(BaseModel):
    artifacts: list[ArtifactRecord]


class SkillListResponse(BaseModel):
    skills: list[SkillMetadata]


class BenchmarkReportIndexEntry(BaseModel):
    benchmark_name: str
    description: str = ""
    paper_hypothesis: str = ""
    primary_metric: str = ""
    generated_at: str = ""
    report_path: str
    manifest_path: str | None = None
    task_count: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)


class BenchmarkReportIndexResponse(BaseModel):
    reports: list[BenchmarkReportIndexEntry]


class ReviewParticipantInput(BaseModel):
    participant_key: str
    participant_type: ReviewParticipantType
    role_label: str


class CreateReviewRequest(BaseModel):
    title: str
    objective: str
    created_by: str
    run_id: UUID | None = None
    artifact_ids: list[UUID] = Field(default_factory=list)
    participants: list[ReviewParticipantInput] = Field(default_factory=list)


class ReviewListResponse(BaseModel):
    reviews: list[ReviewThread]


class ReviewDetailResponse(BaseModel):
    review: ReviewThreadDetail


class ReviewPostListResponse(BaseModel):
    posts: list[ReviewPost]


class CreateReviewPostRequest(BaseModel):
    author_key: str
    author_type: ReviewParticipantType
    body: str
    role_label: str | None = None
    parent_post_id: UUID | None = None


class ReviewRoundRequest(BaseModel):
    mode: ReviewRoundMode = ReviewRoundMode.MODERATED_PANEL
    participant_keys: list[str] = Field(default_factory=list)
    execute_inline: bool = False


class ReviewRoundResponse(BaseModel):
    round: ReviewRound


class ResolveReviewRequest(BaseModel):
    status: ReviewStatus
    resolution_summary: str
    resolved_by: str = "system"


class LiteratureResearchRequest(BaseModel):
    mode: ResearchMode | None = None
    topic: str
    papers: list[LiteraturePaperInput] = Field(default_factory=list)
    notes: str | None = None
    include_markdown: bool = True


class LiteratureResearchResponse(BaseModel):
    result: LiteratureResearchResult


class PeptideResearchRequest(BaseModel):
    mode: ResearchMode | None = None
    prompt: str
    notes: str | None = None
    application_area: str = "cosmetic"
    max_reference_peptides: int = Field(default=5, ge=1, le=10)
    max_candidates: int = Field(default=3, ge=0, le=10)
    benchmark: PeptideBenchmarkExpectation | None = None
    include_markdown: bool = True


class PeptideResearchResponse(BaseModel):
    result: PeptideResearchResult
