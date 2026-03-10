from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from itertools import combinations
from typing import Any, Protocol, TypeVar

from autolab.agents.arxiv import ArxivClient, ArxivClientProtocol, extract_arxiv_id
from autolab.agents.literature_models import (
    AssumptionRecord,
    CitationChain,
    CitationChainStageResult,
    ClaimRecord,
    ContradictionRecord,
    ContradictionStageResult,
    FieldSynthesis,
    GapStageResult,
    IntakeResult,
    KnowledgeMap,
    LiteraturePaperInput,
    LiteratureResearchRequest,
    LiteratureResearchResult,
    LiteratureStageStatus,
    MethodCategorySummary,
    MethodologyAudit,
    MethodRecord,
    PaperCluster,
    PaperDigest,
    PaperRecord,
    ResearchGap,
    SoWhatSummary,
)
from autolab.core.enums import ResearchMode
from autolab.core.settings import Settings
from autolab.telemetry import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

STAGE_ORDER = (
    "intake_protocol",
    "contradiction_finder",
    "citation_chain",
    "gap_scanner",
    "methodology_audit",
    "master_synthesis",
    "assumption_killer",
    "knowledge_map_builder",
    "so_what_test",
)

_LITERATURE_INTENT_PHRASES = {
    "review the literature",
    "analyze papers",
    "find research gaps",
    "compare papers",
    "literature review",
    "literature research",
    "research gaps",
    "citation chain",
}
_STOPWORDS = {
    "about",
    "after",
    "also",
    "among",
    "analysis",
    "based",
    "between",
    "data",
    "field",
    "from",
    "have",
    "into",
    "literature",
    "method",
    "methods",
    "model",
    "paper",
    "papers",
    "results",
    "show",
    "study",
    "their",
    "there",
    "these",
    "this",
    "using",
    "with",
}
_METHOD_KEYWORDS = {
    "experiments": ("experiment", "experimental", "measured", "measurement", "fabricated"),
    "simulations": ("simulation", "simulated", "monte carlo", "finite element", "numerical"),
    "theory": ("theory", "theoretical", "analytical", "formalism", "derive"),
    "surveys": ("survey", "questionnaire", "interview"),
    "meta_analyses": ("meta-analysis", "systematic review", "review article"),
    "case_studies": ("case study", "case-study"),
}
_ASSUMPTION_KEYWORDS = (
    "assume",
    "assuming",
    "assumption",
    "idealized",
    "approximation",
    "constant",
    "fixed",
    "homogeneous",
    "stationary",
    "iid",
)
_POSITIVE_TERMS = {
    "improves",
    "increase",
    "increases",
    "higher",
    "outperform",
    "stable",
    "supports",
}
_NEGATIVE_TERMS = {
    "decrease",
    "decreases",
    "lower",
    "fails",
    "limited",
    "unstable",
    "does not",
}
_STANDARD_METHODS = (
    "experiments",
    "simulations",
    "theory",
    "surveys",
    "meta_analyses",
    "case_studies",
)


class SwarmPayloadBuilderProtocol(Protocol):
    def build_from_literature(self, result: LiteratureResearchResult) -> dict[str, Any]: ...


def detect_research_mode(request: LiteratureResearchRequest) -> ResearchMode | None:
    if request.mode == ResearchMode.LITERATURE_RESEARCH:
        return ResearchMode.LITERATURE_RESEARCH
    haystacks = [request.topic.lower(), (request.notes or "").lower()]
    paper_like_input = False
    for paper in request.papers:
        for value in (paper.arxiv_id, paper.url, paper.title, paper.abstract):
            if value:
                haystacks.append(value.lower())
                paper_like_input = True
        if paper.arxiv_id or (paper.url and extract_arxiv_id(paper.url)):
            return ResearchMode.LITERATURE_RESEARCH
    if any(phrase in "\n".join(haystacks) for phrase in _LITERATURE_INTENT_PHRASES):
        return ResearchMode.LITERATURE_RESEARCH
    if paper_like_input:
        return ResearchMode.LITERATURE_RESEARCH
    return None


class LiteratureResearchService:
    def __init__(self, settings: Settings, arxiv_client: ArxivClientProtocol | None = None) -> None:
        self._settings = settings
        self._arxiv_client = arxiv_client or ArxivClient(settings)

    def run(self, request: LiteratureResearchRequest) -> LiteratureResearchResult:
        mode = detect_research_mode(request)
        if mode != ResearchMode.LITERATURE_RESEARCH:
            msg = "request does not contain literature-research intent"
            raise ValueError(msg)
        papers = self._normalize_papers(request.papers)
        if not papers:
            msg = "literature research requires at least one arXiv paper or paper description"
            raise ValueError(msg)

        stage_status: list[LiteratureStageStatus] = []
        errors: list[str] = []
        limited_confidence = len(papers) == 1

        intake = self._run_stage(
            "intake_protocol",
            lambda: self._build_intake(papers, limited_confidence=limited_confidence),
            lambda exc: IntakeResult(
                papers=[],
                clusters=[],
                warnings=[f"intake degraded: {exc}"],
                limited_confidence=limited_confidence,
            ),
            stage_status,
            errors,
        )
        contradictions = self._run_stage(
            "contradiction_finder",
            lambda: self._build_contradictions(papers),
            lambda exc: ContradictionStageResult(
                contradictions=[
                    ContradictionRecord(
                        concept="analysis degraded",
                        position_a="Contradiction analysis was unavailable.",
                        papers_a=[],
                        position_b="Fallback result emitted to preserve pipeline continuity.",
                        papers_b=[],
                        disagreement_source="interpretation",
                        evidence_note=str(exc),
                        confidence="low",
                    )
                ]
            ),
            stage_status,
            errors,
        )
        citation_chains = self._run_stage(
            "citation_chain",
            lambda: self._build_citation_chains(papers, contradictions),
            lambda exc: CitationChainStageResult(
                citation_chains=[
                    CitationChain(
                        concept="analysis degraded",
                        introduced_by=[],
                        challenged_by=[],
                        refined_by=[],
                        current_consensus="Citation-chain construction degraded for this request.",
                        evidence_note=str(exc),
                    )
                ]
            ),
            stage_status,
            errors,
        )
        gaps = self._run_stage(
            "gap_scanner",
            lambda: self._build_gaps(papers, contradictions),
            lambda exc: GapStageResult(
                gaps=[
                    ResearchGap(
                        question=f"What evidence is still missing for {request.topic}?",
                        why_open="Gap analysis degraded before the paper set could be synthesized.",
                        closest_papers=[],
                        suggested_next_step=(
                            "Collect additional papers and rerun the literature workflow."
                        ),
                        evidence_note=str(exc),
                    )
                ]
            ),
            stage_status,
            errors,
        )
        methodology_audit = self._run_stage(
            "methodology_audit",
            lambda: self._build_methodology_audit(papers, contradictions),
            lambda exc: MethodologyAudit(
                method_groups=[],
                dominant_methods=[],
                underused_methods=[],
                method_sensitive_conclusions=[f"Methodology audit degraded: {exc}"],
            ),
            stage_status,
            errors,
        )
        synthesis = self._run_stage(
            "master_synthesis",
            lambda: self._build_synthesis(papers, contradictions, gaps, limited_confidence),
            lambda exc: FieldSynthesis(
                collective_beliefs=[],
                contested_questions=[],
                shared_assumptions=[],
                promising_next_steps=[],
                evidence_note=f"Synthesis degraded: {exc}",
                confidence="low",
            ),
            stage_status,
            errors,
        )
        assumptions = self._run_stage(
            "assumption_killer",
            lambda: self._build_assumptions(papers, synthesis),
            lambda exc: [
                AssumptionRecord(
                    assumption="The available evidence is sufficient to support synthesis.",
                    evidence="Fallback assumption emitted after stage degradation.",
                    impact_if_false=str(exc),
                )
            ],
            stage_status,
            errors,
        )
        knowledge_map = self._run_stage(
            "knowledge_map_builder",
            lambda: self._build_knowledge_map(synthesis, contradictions, gaps, intake),
            lambda exc: KnowledgeMap(
                central_claim=f"Knowledge map degraded for topic '{request.topic}'.",
                supporting_pillars=[],
                contested_zones=[str(exc)],
                frontier_questions=[],
            ),
            stage_status,
            errors,
        )
        so_what = self._run_stage(
            "so_what_test",
            lambda: self._build_so_what(request.topic, knowledge_map, gaps, limited_confidence),
            lambda exc: SoWhatSummary(
                proven=f"Evidence for {request.topic} could not be fully synthesized.",
                unknown="The unresolved questions remain underspecified due to stage degradation.",
                matters=str(exc),
            ),
            stage_status,
            errors,
        )

        markdown_rendering = None
        if request.include_markdown:
            markdown_rendering = self._render_markdown(
                topic=request.topic,
                intake=intake,
                contradictions=contradictions.contradictions,
                gaps=gaps.gaps,
                methodology_audit=methodology_audit,
                synthesis=synthesis,
                knowledge_map=knowledge_map,
                so_what=so_what,
            )

        return LiteratureResearchResult(
            topic=request.topic,
            papers=papers,
            intake=intake,
            contradictions=contradictions.contradictions,
            citation_chains=citation_chains.citation_chains,
            gaps=gaps.gaps,
            methodology_audit=methodology_audit,
            synthesis=synthesis,
            assumptions=assumptions,
            knowledge_map=knowledge_map,
            so_what=so_what,
            stage_status=stage_status,
            errors=errors,
            markdown_rendering=markdown_rendering,
            swarm_payload=None,
        )

    def _normalize_papers(self, paper_inputs: Sequence[LiteraturePaperInput]) -> list[PaperRecord]:
        resolved = self._arxiv_client.resolve_inputs(paper_inputs)
        deduped: dict[str, PaperRecord] = {}
        duplicate_keys: set[str] = set()
        for paper in resolved:
            key = paper.arxiv_id or paper.paper_id
            if key in deduped:
                duplicate_keys.add(key)
                existing = deduped[key]
                if paper.notes:
                    existing.notes = (
                        paper.notes if not existing.notes else f"{existing.notes}\n{paper.notes}"
                    )
                existing.flags.append("duplicate_reference")
                continue
            if not paper.authors:
                paper.flags.append("missing_authors")
                paper.metadata_quality = "partial"
            if paper.year is None:
                paper.flags.append("missing_year")
                paper.metadata_quality = "partial"
            paper.core_claims = self._extract_claims(paper)
            paper.methods = self._extract_methods(paper)
            paper.assumptions = self._extract_assumptions(paper)
            deduped[key] = paper
        for key in duplicate_keys:
            deduped[key].flags.append("duplicate_reference")
        return sorted(
            deduped.values(),
            key=lambda paper: (paper.year or 9999, paper.title.lower()),
        )

    def _build_intake(
        self, papers: Sequence[PaperRecord], *, limited_confidence: bool
    ) -> IntakeResult:
        digests = [
            PaperDigest(
                paper_id=paper.paper_id,
                author_summary=self._author_summary(paper),
                year=paper.year,
                core_claim=paper.core_claims[0].statement if paper.core_claims else paper.title,
            )
            for paper in papers
        ]
        clusters_by_label: dict[str, PaperCluster] = {}
        for paper in papers:
            label = self._top_theme(paper) or self._primary_method_label(paper)
            cluster = clusters_by_label.setdefault(
                label,
                PaperCluster(
                    label=label,
                    paper_ids=[],
                    shared_themes=[],
                    shared_methods=[],
                    shared_assumptions=[],
                ),
            )
            cluster.paper_ids.append(paper.paper_id)
            cluster.shared_themes = self._merge_unique(
                cluster.shared_themes, self._paper_themes(paper)
            )
            cluster.shared_methods = self._merge_unique(
                cluster.shared_methods, [method.category for method in paper.methods]
            )
            cluster.shared_assumptions = self._merge_unique(
                cluster.shared_assumptions,
                [assumption.assumption for assumption in paper.assumptions[:2]],
            )
        warnings: list[str] = []
        if limited_confidence:
            warnings.append("Only one paper was available, so confidence is limited.")
        warnings.extend(
            f"{paper.paper_id}: weak metadata ({', '.join(paper.flags)})"
            for paper in papers
            if paper.flags
        )
        return IntakeResult(
            papers=digests,
            clusters=list(clusters_by_label.values()),
            warnings=warnings,
            limited_confidence=limited_confidence,
        )

    def _build_contradictions(self, papers: Sequence[PaperRecord]) -> ContradictionStageResult:
        contradictions: list[ContradictionRecord] = []
        for left, right in combinations(papers, 2):
            shared_themes = sorted(set(self._paper_themes(left)) & set(self._paper_themes(right)))
            if not shared_themes:
                continue
            left_claim = left.core_claims[0].statement if left.core_claims else left.title
            right_claim = right.core_claims[0].statement if right.core_claims else right.title
            left_polarity = self._claim_polarity(left_claim)
            right_polarity = self._claim_polarity(right_claim)
            if left_polarity == 0 or right_polarity == 0 or left_polarity == right_polarity:
                continue
            disagreement_source = (
                "methods"
                if self._primary_method_label(left) != self._primary_method_label(right)
                else "interpretation"
            )
            contradictions.append(
                ContradictionRecord(
                    concept=shared_themes[0],
                    position_a=left_claim,
                    papers_a=[left.paper_id],
                    position_b=right_claim,
                    papers_b=[right.paper_id],
                    disagreement_source=disagreement_source,
                    evidence_note=(
                        "Contradiction inferred from opposed claim polarity "
                        "on an overlapping theme."
                    ),
                    confidence="medium",
                )
            )
        return ContradictionStageResult(contradictions=contradictions)

    def _build_citation_chains(
        self, papers: Sequence[PaperRecord], contradictions: ContradictionStageResult
    ) -> CitationChainStageResult:
        chains: list[CitationChain] = []
        for concept in self._central_concepts(papers):
            relevant = [paper for paper in papers if concept in self._paper_themes(paper)]
            if not relevant:
                continue
            ordered = sorted(relevant, key=lambda paper: (paper.year or 9999, paper.title.lower()))
            challenged = [
                paper.paper_id
                for paper in relevant
                if any(
                    contradiction.concept == concept
                    and paper.paper_id in (*contradiction.papers_a, *contradiction.papers_b)
                    for contradiction in contradictions.contradictions
                )
            ]
            refined = [paper.paper_id for paper in ordered[1:] if paper.paper_id not in challenged]
            consensus = self._consensus_statement(ordered, concept)
            chains.append(
                CitationChain(
                    concept=concept,
                    introduced_by=[ordered[0].paper_id],
                    challenged_by=challenged,
                    refined_by=refined,
                    current_consensus=consensus,
                    evidence_note=(
                        "Chain inferred from within-set chronology and thematic overlap; "
                        "no external citation graph enrichment was applied."
                    ),
                )
            )
        return CitationChainStageResult(citation_chains=chains)

    def _build_gaps(
        self, papers: Sequence[PaperRecord], contradictions: ContradictionStageResult
    ) -> GapStageResult:
        gaps: list[ResearchGap] = [
            ResearchGap(
                question=f"What explains the disagreement on {contradiction.concept}?",
                why_open=(
                    "The current paper set reaches conflicting conclusions on the same theme."
                ),
                closest_papers=self._merge_unique(contradiction.papers_a, contradiction.papers_b),
                suggested_next_step=(
                    "Run a matched comparison that aligns definitions and methods "
                    f"across the {contradiction.concept} studies."
                ),
                evidence_note=contradiction.evidence_note,
            )
            for contradiction in contradictions.contradictions
        ]
        for paper in papers:
            for sentence in self._sentences(paper.abstract):
                lowered = sentence.lower()
                if (
                    "future work" in lowered
                    or "remains unclear" in lowered
                    or "open question" in lowered
                ):
                    gaps.append(
                        ResearchGap(
                            question=sentence.rstrip("."),
                            why_open="The paper explicitly identifies this as unresolved.",
                            closest_papers=[paper.paper_id],
                            suggested_next_step=self._suggest_next_step(paper),
                            evidence_note=(
                                "Gap drawn directly from explicit uncertainty "
                                "language in the abstract."
                            ),
                        )
                    )
                    break
        if len(papers) == 1:
            gaps.append(
                ResearchGap(
                    question=(
                        "Can the reported result be reproduced across independent "
                        "datasets or setups?"
                    ),
                    why_open="The evidence base contains only a single paper.",
                    closest_papers=[papers[0].paper_id],
                    suggested_next_step=(
                        "Add at least one independent paper or benchmark replication "
                        "on the same question."
                    ),
                    evidence_note=(
                        "Single-paper evidence cannot support strong field-level certainty."
                    ),
                )
            )
        return GapStageResult(gaps=self._dedupe_gaps(gaps))

    def _build_methodology_audit(
        self, papers: Sequence[PaperRecord], contradictions: ContradictionStageResult
    ) -> MethodologyAudit:
        grouped: dict[str, list[MethodRecord]] = defaultdict(list)
        for paper in papers:
            for method in paper.methods:
                grouped[method.category].append(method)
        summaries: list[MethodCategorySummary] = []
        dominant_methods: list[str] = []
        if grouped:
            max_count = max(len(records) for records in grouped.values())
            dominant_methods = [
                category for category, records in grouped.items() if len(records) == max_count
            ]
        for category, records in sorted(grouped.items()):
            summaries.append(
                MethodCategorySummary(
                    category=category,
                    paper_ids=[record.paper_id for record in records],
                    dominant=category in dominant_methods,
                    likely_biases=self._merge_unique(
                        [], [bias for record in records for bias in record.likely_biases]
                    ),
                )
            )
        underused = [category for category in _STANDARD_METHODS if category not in grouped][:2]
        method_sensitive_conclusions = [
            (
                f"{contradiction.concept}: disagreement may depend on "
                f"{contradiction.disagreement_source}."
            )
            for contradiction in contradictions.contradictions
            if contradiction.disagreement_source == "methods"
        ]
        return MethodologyAudit(
            method_groups=summaries,
            dominant_methods=dominant_methods,
            underused_methods=underused,
            method_sensitive_conclusions=method_sensitive_conclusions,
        )

    def _build_synthesis(
        self,
        papers: Sequence[PaperRecord],
        contradictions: ContradictionStageResult,
        gaps: GapStageResult,
        limited_confidence: bool,
    ) -> FieldSynthesis:
        collective_beliefs = [
            claim.statement for paper in papers for claim in paper.core_claims[:1]
        ][:3]
        if limited_confidence:
            collective_beliefs = (
                [f"Single-paper evidence suggests: {collective_beliefs[0]}"]
                if collective_beliefs
                else []
            )
        contested_questions = [
            f"{item.concept}: {item.position_a} vs {item.position_b}"
            for item in contradictions.contradictions[:3]
        ]
        shared_assumptions = self._aggregate_assumptions(papers)
        promising_next_steps = [gap.suggested_next_step for gap in gaps.gaps[:3]]
        confidence = "low" if limited_confidence else "medium"
        if len(papers) >= 4 and not contradictions.contradictions:
            confidence = "high"
        return FieldSynthesis(
            collective_beliefs=collective_beliefs,
            contested_questions=contested_questions,
            shared_assumptions=shared_assumptions,
            promising_next_steps=promising_next_steps,
            evidence_note=(
                "Synthesis is constrained to the provided arXiv-centered paper set "
                "and does not use an external citation corpus."
            ),
            confidence=confidence,
        )

    def _build_assumptions(
        self, papers: Sequence[PaperRecord], synthesis: FieldSynthesis
    ) -> list[AssumptionRecord]:
        assumptions: list[AssumptionRecord] = []
        for paper in papers:
            assumptions.extend(paper.assumptions)
        if not assumptions and synthesis.shared_assumptions:
            assumptions = [
                AssumptionRecord(
                    assumption=value,
                    evidence="Assumption surfaced from shared synthesis patterns.",
                    impact_if_false=(
                        "The current synthesis would need to be re-evaluated "
                        "against more diverse evidence."
                    ),
                )
                for value in synthesis.shared_assumptions
            ]
        return assumptions[:5]

    def _build_knowledge_map(
        self,
        synthesis: FieldSynthesis,
        contradictions: ContradictionStageResult,
        gaps: GapStageResult,
        intake: IntakeResult,
    ) -> KnowledgeMap:
        central_claim = (
            synthesis.collective_beliefs[0]
            if synthesis.collective_beliefs
            else "The literature set is too sparse to support a strong central claim."
        )
        supporting_pillars = synthesis.collective_beliefs[:5]
        if len(supporting_pillars) < 3:
            supporting_pillars = self._merge_unique(
                supporting_pillars, [cluster.label for cluster in intake.clusters[:3]]
            )
        contested_zones = [item.concept for item in contradictions.contradictions[:3]]
        frontier_questions = [gap.question for gap in gaps.gaps[:2]]
        return KnowledgeMap(
            central_claim=central_claim,
            supporting_pillars=supporting_pillars[:5],
            contested_zones=contested_zones[:3],
            frontier_questions=frontier_questions[:2],
        )

    def _build_so_what(
        self,
        topic: str,
        knowledge_map: KnowledgeMap,
        gaps: GapStageResult,
        limited_confidence: bool,
    ) -> SoWhatSummary:
        proven = knowledge_map.central_claim
        unknown = (
            gaps.gaps[0].question
            if gaps.gaps
            else "Important open questions remain under-specified."
        )
        matters = (
            f"This matters for {topic} because downstream modeling, experimentation, "
            "and resource allocation depend on which parts of the evidence are robust."
        )
        if limited_confidence:
            proven = f"Preliminary evidence suggests: {proven}"
        return SoWhatSummary(proven=proven, unknown=unknown, matters=matters)

    def _render_markdown(
        self,
        *,
        topic: str,
        intake: IntakeResult,
        contradictions: Sequence[ContradictionRecord],
        gaps: Sequence[ResearchGap],
        methodology_audit: MethodologyAudit,
        synthesis: FieldSynthesis,
        knowledge_map: KnowledgeMap,
        so_what: SoWhatSummary,
    ) -> str:
        lines = [
            f"# Literature Research: {topic}",
            "",
            "## Intake",
            *[
                f"- {paper.author_summary} ({paper.year or 'n.d.'}): {paper.core_claim}"
                for paper in intake.papers
            ],
            "",
            "## Contradictions",
            *(
                [
                    f"- {item.concept}: {item.position_a} vs {item.position_b}"
                    for item in contradictions
                ]
                or ["- No direct contradictions detected in the provided set."]
            ),
            "",
            "## Methodology Audit",
            *(
                [
                    f"- {group.category}: {', '.join(group.paper_ids)}"
                    for group in methodology_audit.method_groups
                ]
                or ["- No methodology groups identified."]
            ),
            "",
            "## Synthesis",
            *(
                [f"- {belief}" for belief in synthesis.collective_beliefs]
                or ["- No synthesis available."]
            ),
            "",
            "## Knowledge Map",
            f"- Central claim: {knowledge_map.central_claim}",
            *[f"- Supporting pillar: {pillar}" for pillar in knowledge_map.supporting_pillars],
            *[f"- Contested zone: {zone}" for zone in knowledge_map.contested_zones],
            *[f"- Frontier question: {question}" for question in knowledge_map.frontier_questions],
            "",
            "## So What",
            f"- Proven: {so_what.proven}",
            f"- Unknown: {so_what.unknown}",
            f"- Why it matters: {so_what.matters}",
        ]
        if gaps:
            insertion = lines.index("## Knowledge Map")
            gap_lines = ["## Research Gaps", *[f"- {gap.question}" for gap in gaps], ""]
            lines[insertion:insertion] = gap_lines
        return "\n".join(lines)

    def _run_stage(
        self,
        stage_name: str,
        builder: Callable[[], T],
        fallback: Callable[[Exception], T],
        stage_status: list[LiteratureStageStatus],
        errors: list[str],
    ) -> T:
        try:
            result = builder()
            warnings = list(result.warnings) if isinstance(result, IntakeResult) else []
            stage_status.append(
                LiteratureStageStatus(stage=stage_name, status="complete", warnings=warnings)
            )
            return result
        except Exception as exc:
            logger.exception("literature stage %s degraded", stage_name, error=str(exc))
            errors.append(f"{stage_name}: {exc}")
            degraded = fallback(exc)
            stage_status.append(
                LiteratureStageStatus(stage=stage_name, status="degraded", errors=[str(exc)])
            )
            return degraded

    def _extract_claims(self, paper: PaperRecord) -> list[ClaimRecord]:
        sentence = self._claim_sentence(paper.abstract) or paper.title
        evidence_type = "stated" if paper.abstract else "inferred"
        return [
            ClaimRecord(
                paper_id=paper.paper_id,
                statement=sentence,
                evidence=paper.abstract or paper.title,
                evidence_type=evidence_type,
                confidence="medium" if paper.abstract else "low",
            )
        ]

    def _extract_methods(self, paper: PaperRecord) -> list[MethodRecord]:
        text = " ".join(part for part in (paper.title, paper.abstract, paper.notes or "") if part)
        category = self._classify_method(text)
        evidence = next(
            (
                sentence
                for sentence in self._sentences(text)
                if any(
                    keyword in sentence.lower() for keyword in _METHOD_KEYWORDS.get(category, ())
                )
            ),
            self._claim_sentence(text) or text,
        )
        return [
            MethodRecord(
                paper_id=paper.paper_id,
                category=category,
                method=category.replace("_", " "),
                evidence=evidence,
                likely_biases=self._biases_for_method(category),
            )
        ]

    def _extract_assumptions(self, paper: PaperRecord) -> list[AssumptionRecord]:
        assumptions: list[AssumptionRecord] = []
        for sentence in self._sentences(
            " ".join(part for part in (paper.abstract, paper.notes or "") if part)
        ):
            lowered = sentence.lower()
            if any(keyword in lowered for keyword in _ASSUMPTION_KEYWORDS):
                assumptions.append(
                    AssumptionRecord(
                        paper_id=paper.paper_id,
                        assumption=sentence.rstrip("."),
                        evidence=sentence,
                        impact_if_false=(
                            "The paper's conclusion may not generalize beyond the assumed regime."
                        ),
                    )
                )
        if not assumptions:
            assumptions.append(
                AssumptionRecord(
                    paper_id=paper.paper_id,
                    assumption=(
                        f"The {self._primary_method_label(paper)} setup is "
                        "representative of the broader problem."
                    ),
                    evidence="Inferred from the paper's primary methodology.",
                    impact_if_false=(
                        "The reported conclusion could be specific to the chosen "
                        "setup rather than the field."
                    ),
                )
            )
        return assumptions[:2]

    def _author_summary(self, paper: PaperRecord) -> str:
        if not paper.authors:
            return "Unknown authors"
        if len(paper.authors) == 1:
            return paper.authors[0].name
        return f"{paper.authors[0].name} et al."

    def _paper_themes(self, paper: PaperRecord) -> list[str]:
        tokens = self._keywords(" ".join(part for part in (paper.title, paper.abstract) if part))
        return tokens[:4] or ["general"]

    def _top_theme(self, paper: PaperRecord) -> str:
        themes = self._paper_themes(paper)
        return themes[0] if themes else "general"

    def _central_concepts(self, papers: Sequence[PaperRecord]) -> list[str]:
        counts: Counter[str] = Counter()
        for paper in papers:
            counts.update(self._paper_themes(paper))
        return [concept for concept, _ in counts.most_common(3)]

    def _consensus_statement(self, papers: Sequence[PaperRecord], concept: str) -> str:
        polarities = [
            self._claim_polarity(paper.core_claims[0].statement)
            for paper in papers
            if paper.core_claims
        ]
        if not polarities:
            return f"Consensus on {concept} is unclear from the available set."
        positive = len([value for value in polarities if value > 0])
        negative = len([value for value in polarities if value < 0])
        if positive > negative:
            return (
                f"Most papers in this set support {concept}, but the evidence remains "
                "bounded by the provided corpus."
            )
        if negative > positive:
            return (
                f"Most papers in this set challenge or limit {concept}, "
                "but the evidence remains bounded by the provided corpus."
            )
        return f"The current set shows no stable consensus on {concept}."

    def _suggest_next_step(self, paper: PaperRecord) -> str:
        category = self._primary_method_label(paper)
        if category == "simulations":
            return (
                "Validate the simulated effect with a matched experiment or a stronger benchmark."
            )
        if category == "experiments":
            return (
                "Replicate the finding under controlled variants and compare "
                "against a mechanistic model."
            )
        return "Collect a second method family on the same question to test robustness."

    def _aggregate_assumptions(self, papers: Sequence[PaperRecord]) -> list[str]:
        counts: Counter[str] = Counter()
        for paper in papers:
            counts.update(assumption.assumption for assumption in paper.assumptions)
        return [assumption for assumption, _ in counts.most_common(3)]

    def _claim_sentence(self, text: str) -> str | None:
        sentences = self._sentences(text)
        return sentences[0] if sentences else None

    def _sentences(self, text: str) -> list[str]:
        cleaned = " ".join(text.split())
        if not cleaned:
            return []
        parts = [part.strip() for part in cleaned.replace("?", ".").replace("!", ".").split(".")]
        return [part for part in parts if part]

    def _classify_method(self, text: str) -> str:
        lowered = text.lower()
        for category, keywords in _METHOD_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return category
        return "theory"

    def _biases_for_method(self, category: str) -> list[str]:
        biases = {
            "experiments": ["apparatus sensitivity", "sample-selection effects"],
            "simulations": ["model misspecification", "boundary-condition sensitivity"],
            "theory": ["idealized assumptions", "limited empirical grounding"],
            "surveys": ["response bias", "recall bias"],
            "meta_analyses": ["publication bias", "study-selection bias"],
            "case_studies": ["low external validity", "selection effects"],
        }
        return list(biases.get(category, ["method-specific bias"]))

    def _claim_polarity(self, claim: str) -> int:
        lowered = claim.lower()
        positive_hits = sum(term in lowered for term in _POSITIVE_TERMS)
        negative_hits = sum(term in lowered for term in _NEGATIVE_TERMS)
        if positive_hits > negative_hits:
            return 1
        if negative_hits > positive_hits:
            return -1
        return 0

    def _keywords(self, text: str) -> list[str]:
        counts: Counter[str] = Counter()
        for raw in text.lower().replace("/", " ").replace("-", " ").split():
            token = "".join(character for character in raw if character.isalpha())
            if len(token) < 4 or token in _STOPWORDS:
                continue
            counts[token] += 1
        return [token for token, _ in counts.most_common(6)]

    def _primary_method_label(self, paper: PaperRecord) -> str:
        return paper.methods[0].category if paper.methods else "theory"

    def _merge_unique(self, existing: list[str], incoming: Iterable[str]) -> list[str]:
        ordered = list(existing)
        seen = set(existing)
        for item in incoming:
            if item and item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered

    def _dedupe_gaps(self, gaps: Sequence[ResearchGap]) -> list[ResearchGap]:
        deduped: dict[str, ResearchGap] = {}
        for gap in gaps:
            key = gap.question.lower()
            if key not in deduped:
                deduped[key] = gap
        return list(deduped.values())[:5]
