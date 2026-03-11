from __future__ import annotations

from typing import Any, Literal

from autolab.core.enums import ResearchMode
from autolab.core.models import AutolabModel
from pydantic import Field


class PeptideBenchmarkExpectation(AutolabModel):
    claim_clusters: list[str] = Field(default_factory=list)
    mechanisms: list[str] = Field(default_factory=list)
    families: list[str] = Field(default_factory=list)


class ClaimClusterMatch(AutolabModel):
    claim_cluster: str
    score: float
    matched_terms: list[str] = Field(default_factory=list)
    rationale: str


class MechanismMatch(AutolabModel):
    mechanism: str
    score: float
    supporting_claim_clusters: list[str] = Field(default_factory=list)
    rationale: str


class PeptideDescriptor(AutolabModel):
    length: int
    net_charge: int
    hydrophobic_fraction: float
    aromatic_fraction: float


class PeptideCitation(AutolabModel):
    citation_id: str
    title: str
    year: int
    journal: str
    url: str
    doi: str | None = None
    pmid: str | None = None
    evidence_type: str = "review"
    supports: list[str] = Field(default_factory=list)


class PeptideEvidence(AutolabModel):
    tier: str = "unrated"
    summary: str = ""
    citations: list[PeptideCitation] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class PeptideReferenceRecord(AutolabModel):
    peptide_id: str
    name: str
    sequence: str
    family: str
    claim_clusters: list[str] = Field(default_factory=list)
    mechanisms: list[str] = Field(default_factory=list)
    modifications: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    evidence_level: Literal["marketed", "literature_supported", "exploratory"] = "marketed"
    rationale: str
    evidence: PeptideEvidence = Field(default_factory=PeptideEvidence)


class PeptideReferenceDataset(AutolabModel):
    dataset_id: str
    version: str
    scope: str
    generated_on: str
    description: str
    entries: list[PeptideReferenceRecord] = Field(default_factory=list)


class PeptideReferenceDatasetArtifact(AutolabModel):
    version: str
    filename: str
    dataset_id: str
    scope: str
    description: str = ""


class PeptideReferenceDatasetManifest(AutolabModel):
    default_version: str
    datasets: list[PeptideReferenceDatasetArtifact] = Field(default_factory=list)


class ReferencePeptide(PeptideReferenceRecord):
    descriptors: PeptideDescriptor
    retrieval_score: float = 0.0


class FamilyMatch(AutolabModel):
    family: str
    score: float
    supporting_mechanisms: list[str] = Field(default_factory=list)
    supporting_peptide_ids: list[str] = Field(default_factory=list)
    rationale: str


class CandidateFilterReport(AutolabModel):
    passed: bool
    passed_filters: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CandidatePeptide(AutolabModel):
    candidate_id: str
    sequence: str
    family: str
    derived_from_peptide_id: str
    modifications: list[str] = Field(default_factory=list)
    rationale: str
    descriptors: PeptideDescriptor
    similarity_to_reference: float
    novelty_score: float
    filter_report: CandidateFilterReport


class PeptideBenchmarkSummary(AutolabModel):
    mechanism_match: float
    family_match: float
    descriptor_plausibility: float
    novelty_penalty: float
    market_neighborhood_recall: float
    expectation_match: dict[str, float] | None = None
    notes: list[str] = Field(default_factory=list)


class PeptideResearchRequest(AutolabModel):
    mode: ResearchMode | None = None
    prompt: str
    notes: str | None = None
    application_area: Literal["cosmetic", "therapeutic", "general"] = "cosmetic"
    max_reference_peptides: int = Field(default=5, ge=1, le=10)
    max_candidates: int = Field(default=3, ge=0, le=10)
    benchmark: PeptideBenchmarkExpectation | None = None
    include_markdown: bool = True


class PeptideResearchResult(AutolabModel):
    mode: ResearchMode = ResearchMode.PEPTIDE_RESEARCH
    prompt: str
    application_area: str
    normalized_claims: list[ClaimClusterMatch] = Field(default_factory=list)
    mechanism_rankings: list[MechanismMatch] = Field(default_factory=list)
    family_rankings: list[FamilyMatch] = Field(default_factory=list)
    reference_peptides: list[ReferencePeptide] = Field(default_factory=list)
    candidate_peptides: list[CandidatePeptide] = Field(default_factory=list)
    benchmark: PeptideBenchmarkSummary
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    markdown_rendering: str | None = None
