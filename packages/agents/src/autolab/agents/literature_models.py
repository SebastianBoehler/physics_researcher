from __future__ import annotations

from typing import Any, Literal

from autolab.core.enums import ResearchMode
from autolab.core.models import AutolabModel
from pydantic import Field


class LiteraturePaperInput(AutolabModel):
    arxiv_id: str | None = None
    url: str | None = None
    title: str | None = None
    abstract: str | None = None
    notes: str | None = None


class AuthorRecord(AutolabModel):
    name: str


class ClaimRecord(AutolabModel):
    paper_id: str
    statement: str
    evidence: str
    evidence_type: Literal["stated", "inferred"] = "stated"
    confidence: str = "medium"


class MethodRecord(AutolabModel):
    paper_id: str
    category: str
    method: str
    evidence: str
    likely_biases: list[str] = Field(default_factory=list)


class AssumptionRecord(AutolabModel):
    paper_id: str | None = None
    assumption: str
    evidence: str
    tested: bool = False
    impact_if_false: str


class PaperRecord(AutolabModel):
    paper_id: str
    arxiv_id: str | None = None
    title: str
    abstract: str
    authors: list[AuthorRecord] = Field(default_factory=list)
    year: int | None = None
    url: str | None = None
    pdf_url: str | None = None
    categories: list[str] = Field(default_factory=list)
    notes: str | None = None
    metadata_quality: str = "partial"
    flags: list[str] = Field(default_factory=list)
    core_claims: list[ClaimRecord] = Field(default_factory=list)
    methods: list[MethodRecord] = Field(default_factory=list)
    assumptions: list[AssumptionRecord] = Field(default_factory=list)


class PaperDigest(AutolabModel):
    paper_id: str
    author_summary: str
    year: int | None = None
    core_claim: str


class PaperCluster(AutolabModel):
    label: str
    paper_ids: list[str] = Field(default_factory=list)
    shared_themes: list[str] = Field(default_factory=list)
    shared_methods: list[str] = Field(default_factory=list)
    shared_assumptions: list[str] = Field(default_factory=list)


class IntakeResult(AutolabModel):
    papers: list[PaperDigest] = Field(default_factory=list)
    clusters: list[PaperCluster] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limited_confidence: bool = False


class ContradictionRecord(AutolabModel):
    concept: str
    position_a: str
    papers_a: list[str] = Field(default_factory=list)
    position_b: str
    papers_b: list[str] = Field(default_factory=list)
    disagreement_source: str
    evidence_note: str
    confidence: str = "medium"


class ContradictionStageResult(AutolabModel):
    contradictions: list[ContradictionRecord] = Field(default_factory=list)


class CitationChain(AutolabModel):
    concept: str
    introduced_by: list[str] = Field(default_factory=list)
    challenged_by: list[str] = Field(default_factory=list)
    refined_by: list[str] = Field(default_factory=list)
    current_consensus: str
    evidence_note: str


class CitationChainStageResult(AutolabModel):
    citation_chains: list[CitationChain] = Field(default_factory=list)


class ResearchGap(AutolabModel):
    question: str
    why_open: str
    closest_papers: list[str] = Field(default_factory=list)
    suggested_next_step: str
    evidence_note: str


class GapStageResult(AutolabModel):
    gaps: list[ResearchGap] = Field(default_factory=list)


class MethodCategorySummary(AutolabModel):
    category: str
    paper_ids: list[str] = Field(default_factory=list)
    dominant: bool = False
    likely_biases: list[str] = Field(default_factory=list)


class MethodologyAudit(AutolabModel):
    method_groups: list[MethodCategorySummary] = Field(default_factory=list)
    dominant_methods: list[str] = Field(default_factory=list)
    underused_methods: list[str] = Field(default_factory=list)
    method_sensitive_conclusions: list[str] = Field(default_factory=list)


class FieldSynthesis(AutolabModel):
    collective_beliefs: list[str] = Field(default_factory=list)
    contested_questions: list[str] = Field(default_factory=list)
    shared_assumptions: list[str] = Field(default_factory=list)
    promising_next_steps: list[str] = Field(default_factory=list)
    evidence_note: str
    confidence: str = "medium"


class AssumptionStageResult(AutolabModel):
    assumptions: list[AssumptionRecord] = Field(default_factory=list)


class KnowledgeMap(AutolabModel):
    central_claim: str
    supporting_pillars: list[str] = Field(default_factory=list)
    contested_zones: list[str] = Field(default_factory=list)
    frontier_questions: list[str] = Field(default_factory=list)


class SoWhatSummary(AutolabModel):
    proven: str
    unknown: str
    matters: str


class LiteratureStageStatus(AutolabModel):
    stage: str
    status: Literal["complete", "degraded", "failed"]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LiteratureResearchRequest(AutolabModel):
    mode: ResearchMode | None = None
    topic: str
    papers: list[LiteraturePaperInput] = Field(default_factory=list)
    notes: str | None = None
    include_markdown: bool = True


class LiteratureResearchResult(AutolabModel):
    mode: ResearchMode = ResearchMode.LITERATURE_RESEARCH
    topic: str
    papers: list[PaperRecord] = Field(default_factory=list)
    intake: IntakeResult
    contradictions: list[ContradictionRecord] = Field(default_factory=list)
    citation_chains: list[CitationChain] = Field(default_factory=list)
    gaps: list[ResearchGap] = Field(default_factory=list)
    methodology_audit: MethodologyAudit
    synthesis: FieldSynthesis
    assumptions: list[AssumptionRecord] = Field(default_factory=list)
    knowledge_map: KnowledgeMap
    so_what: SoWhatSummary
    stage_status: list[LiteratureStageStatus] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    markdown_rendering: str | None = None
    swarm_payload: dict[str, Any] | None = None
