from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Final

from autolab.agents.peptide_models import (
    CandidateFilterReport,
    CandidatePeptide,
    ClaimClusterMatch,
    FamilyMatch,
    MechanismMatch,
    PeptideBenchmarkExpectation,
    PeptideBenchmarkSummary,
    PeptideDescriptor,
    PeptideResearchRequest,
    PeptideResearchResult,
    ReferencePeptide,
)
from autolab.agents.peptide_reference_data import load_reference_dataset
from autolab.core.enums import ResearchMode
from autolab.core.settings import Settings

_CLAIM_RULES: Final[dict[str, dict[str, object]]] = {
    "clearer_skin": {
        "keywords": (
            "clearer skin",
            "clear skin",
            "blemish",
            "breakout",
            "redness",
            "calm skin",
            "soothe skin",
        ),
        "mechanisms": {
            "inflammation_modulation": 1.0,
            "barrier_support": 0.9,
            "repair_signaling": 0.7,
        },
    },
    "fewer_wrinkles": {
        "keywords": (
            "wrinkle",
            "wrinkles",
            "expression line",
            "smoother skin",
            "line softening",
            "anti-aging",
        ),
        "mechanisms": {
            "cosmetic_neuromodulation": 1.0,
            "collagen_signal": 0.8,
            "extracellular_matrix_support": 0.7,
        },
    },
    "barrier_repair": {
        "keywords": (
            "barrier repair",
            "repair",
            "skin barrier",
            "recovery",
            "resilience",
        ),
        "mechanisms": {
            "barrier_support": 1.0,
            "repair_signaling": 0.9,
            "collagen_signal": 0.4,
        },
    },
    "firmer_skin": {
        "keywords": (
            "firm",
            "firmness",
            "firmer skin",
            "elasticity",
            "lifted",
        ),
        "mechanisms": {
            "collagen_signal": 1.0,
            "extracellular_matrix_support": 0.9,
            "repair_signaling": 0.5,
        },
    },
    "faster_muscle_recovery": {
        "keywords": (
            "muscle recovery",
            "recovery after training",
            "faster recovery",
            "athletic recovery",
        ),
        "mechanisms": {
            "regenerative_support": 1.0,
            "anabolic_recovery": 0.9,
            "inflammation_modulation": 0.5,
        },
    },
    "memory_support": {
        "keywords": (
            "memory support",
            "memory",
            "cognitive support",
            "focus",
            "learning",
        ),
        "mechanisms": {
            "neurotrophic_support": 1.0,
            "receptor_modulation": 0.8,
        },
    },
}
_PEPTIDE_KEYWORDS: Final[tuple[str, ...]] = (
    "peptide",
    "wrinkle",
    "skin",
    "barrier",
    "collagen",
    "repair",
    "argireline",
    "ghk",
    "copper peptide",
)
_HYDROPHOBIC: Final[set[str]] = {"A", "C", "F", "G", "I", "L", "M", "P", "V", "W", "Y"}
_AROMATIC: Final[set[str]] = {"F", "W", "Y"}
_POSITIVE: Final[set[str]] = {"H", "K", "R"}
_NEGATIVE: Final[set[str]] = {"D", "E"}
_SUBSTITUTIONS: Final[dict[str, tuple[str, ...]]] = {
    "A": ("G", "S", "V"),
    "D": ("E", "N"),
    "E": ("D", "Q"),
    "G": ("A", "S"),
    "H": ("K", "Q"),
    "K": ("R", "H", "Q"),
    "M": ("L", "I", "Q"),
    "P": ("A", "G"),
    "Q": ("N", "H", "E"),
    "R": ("K", "Q", "H"),
    "S": ("T", "A", "G"),
    "T": ("S", "A"),
}


def detect_peptide_research_mode(request: PeptideResearchRequest) -> ResearchMode | None:
    if request.mode == ResearchMode.PEPTIDE_RESEARCH:
        return ResearchMode.PEPTIDE_RESEARCH
    haystack = " ".join(
        part.lower() for part in (request.prompt, request.notes or "") if part is not None
    )
    if any(keyword in haystack for keyword in _PEPTIDE_KEYWORDS):
        return ResearchMode.PEPTIDE_RESEARCH
    return None


class PeptideResearchService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._dataset = load_reference_dataset()

    def run(self, request: PeptideResearchRequest) -> PeptideResearchResult:
        mode = detect_peptide_research_mode(request)
        if mode != ResearchMode.PEPTIDE_RESEARCH:
            msg = "request does not contain peptide-research intent"
            raise ValueError(msg)

        prompt = request.prompt.strip()
        if not prompt:
            msg = "peptide research requires a non-empty prompt"
            raise ValueError(msg)

        claims = self._normalize_claims(prompt, request.notes)
        mechanisms = self._rank_mechanisms(claims)
        references = self._retrieve_reference_peptides(
            prompt=prompt,
            application_area=request.application_area,
            claims=claims,
            mechanisms=mechanisms,
            max_items=request.max_reference_peptides,
        )
        families = self._rank_families(references, mechanisms)
        candidates = self._generate_candidates(
            references=references,
            max_items=request.max_candidates,
        )
        benchmark = self._benchmark(
            claims=claims,
            mechanisms=mechanisms,
            families=families,
            references=references,
            candidates=candidates,
            expected=request.benchmark,
        )
        warnings = self._warnings_for_request(request, claims, references)

        result = PeptideResearchResult(
            prompt=prompt,
            application_area=request.application_area,
            normalized_claims=claims,
            mechanism_rankings=mechanisms,
            family_rankings=families,
            reference_peptides=references,
            candidate_peptides=candidates,
            benchmark=benchmark,
            warnings=warnings,
            metadata={
                "reference_library_size": len(self._dataset.entries),
                "dataset_id": self._dataset.dataset_id,
                "dataset_version": self._dataset.version,
                "retrieval_strategy": "claim->mechanism->market-neighborhood",
            },
            markdown_rendering=None,
        )
        if request.include_markdown:
            result.markdown_rendering = self._render_markdown(result)
        return result

    def _normalize_claims(self, prompt: str, notes: str | None) -> list[ClaimClusterMatch]:
        haystack = " ".join(part.lower() for part in (prompt, notes or "")).strip()
        matches: list[ClaimClusterMatch] = []
        for claim_cluster, config in _CLAIM_RULES.items():
            keywords = tuple(config["keywords"])
            matched_terms = [keyword for keyword in keywords if keyword in haystack]
            if matched_terms:
                score = min(1.0, 0.45 + 0.18 * len(matched_terms))
                matches.append(
                    ClaimClusterMatch(
                        claim_cluster=claim_cluster,
                        score=round(score, 3),
                        matched_terms=matched_terms,
                        rationale=(
                            f"Matched {len(matched_terms)} prompt terms to the "
                            f"{claim_cluster} claim cluster."
                        ),
                    )
                )
        if matches:
            return sorted(matches, key=lambda item: item.score, reverse=True)

        fallback_claim = "barrier_repair" if "repair" in haystack else "fewer_wrinkles"
        return [
            ClaimClusterMatch(
                claim_cluster=fallback_claim,
                score=0.34,
                matched_terms=[],
                rationale=(
                    "No direct claim phrase matched, so the pipeline picked the nearest "
                    "high-prior cosmetic cluster as a fallback."
                ),
            )
        ]

    def _rank_mechanisms(self, claims: list[ClaimClusterMatch]) -> list[MechanismMatch]:
        mechanism_scores: Counter[str] = Counter()
        supporting_claims: dict[str, list[str]] = {}
        for claim in claims:
            config = _CLAIM_RULES[claim.claim_cluster]
            for mechanism, weight in dict(config["mechanisms"]).items():
                mechanism_scores[mechanism] += claim.score * float(weight)
                supporting_claims.setdefault(mechanism, []).append(claim.claim_cluster)
        return [
            MechanismMatch(
                mechanism=mechanism,
                score=round(score, 3),
                supporting_claim_clusters=supporting_claims[mechanism],
                rationale=(
                    f"{mechanism} is supported by the matched claim clusters "
                    f"{', '.join(supporting_claims[mechanism])}."
                ),
            )
            for mechanism, score in mechanism_scores.most_common()
        ]

    def _retrieve_reference_peptides(
        self,
        *,
        prompt: str,
        application_area: str,
        claims: list[ClaimClusterMatch],
        mechanisms: list[MechanismMatch],
        max_items: int,
    ) -> list[ReferencePeptide]:
        haystack = prompt.lower()
        claim_lookup = {claim.claim_cluster: claim.score for claim in claims}
        top_mechanisms = {mechanism.mechanism: mechanism.score for mechanism in mechanisms[:4]}
        matches: list[ReferencePeptide] = []
        for raw_reference in self._dataset.entries:
            claim_overlap = sum(
                claim_lookup.get(claim_cluster, 0.0)
                for claim_cluster in raw_reference.claim_clusters
            )
            mechanism_overlap = sum(
                top_mechanisms.get(mechanism, 0.0)
                for mechanism in raw_reference.mechanisms
            )
            alias_bonus = 0.0
            for alias in [*raw_reference.aliases, raw_reference.name]:
                alias_bonus += 0.25 if str(alias).lower() in haystack else 0.0
            area_bonus = 0.1 if application_area == "cosmetic" else 0.0
            retrieval_score = round(
                claim_overlap * 0.45 + mechanism_overlap * 0.45 + alias_bonus + area_bonus,
                3,
            )
            descriptors = self._describe_sequence(raw_reference.sequence)
            matches.append(
                ReferencePeptide(
                    peptide_id=raw_reference.peptide_id,
                    name=raw_reference.name,
                    sequence=raw_reference.sequence,
                    family=raw_reference.family,
                    claim_clusters=raw_reference.claim_clusters,
                    mechanisms=raw_reference.mechanisms,
                    modifications=raw_reference.modifications,
                    aliases=raw_reference.aliases,
                    evidence_level=raw_reference.evidence_level,
                    rationale=raw_reference.rationale,
                    evidence=raw_reference.evidence,
                    descriptors=descriptors,
                    retrieval_score=retrieval_score,
                )
            )
        matches.sort(key=lambda item: item.retrieval_score, reverse=True)
        return matches[:max_items]

    def _rank_families(
        self,
        references: list[ReferencePeptide],
        mechanisms: list[MechanismMatch],
    ) -> list[FamilyMatch]:
        mechanism_lookup = {mechanism.mechanism: mechanism.score for mechanism in mechanisms}
        family_scores: Counter[str] = Counter()
        family_refs: dict[str, list[str]] = {}
        family_mechanisms: dict[str, set[str]] = {}
        for reference in references:
            family_scores[reference.family] += reference.retrieval_score
            family_refs.setdefault(reference.family, []).append(reference.peptide_id)
            family_mechanisms.setdefault(reference.family, set()).update(reference.mechanisms)
        return [
            FamilyMatch(
                family=family,
                score=round(
                    score
                    + sum(
                        mechanism_lookup.get(item, 0.0)
                        for item in family_mechanisms[family]
                    )
                    * 0.2,
                    3,
                ),
                supporting_mechanisms=sorted(family_mechanisms[family]),
                supporting_peptide_ids=family_refs[family],
                rationale=(
                    f"{family} is supported by "
                    f"{len(family_refs[family])} retrieved reference peptides "
                    "and aligns with the dominant mechanism set."
                ),
            )
            for family, score in family_scores.most_common()
        ]

    def _generate_candidates(
        self,
        *,
        references: list[ReferencePeptide],
        max_items: int,
    ) -> list[CandidatePeptide]:
        candidates: list[CandidatePeptide] = []
        seen_sequences: set[str] = set()
        for reference in references:
            if len(candidates) >= max_items:
                break
            mutated_sequence = self._mutate_sequence(reference.sequence)
            if mutated_sequence is None or mutated_sequence in seen_sequences:
                continue
            seen_sequences.add(mutated_sequence)
            descriptors = self._describe_sequence(mutated_sequence)
            similarity = round(self._sequence_similarity(reference.sequence, mutated_sequence), 3)
            novelty = round(1.0 - similarity, 3)
            filter_report = self._filter_candidate(descriptors, novelty)
            candidates.append(
                CandidatePeptide(
                    candidate_id=f"{reference.peptide_id}-variant-{len(candidates) + 1}",
                    sequence=mutated_sequence,
                    family=reference.family,
                    derived_from_peptide_id=reference.peptide_id,
                    modifications=reference.modifications,
                    rationale=(
                        "Conservative single-site mutation that preserves the reference family "
                        "while increasing novelty."
                    ),
                    descriptors=descriptors,
                    similarity_to_reference=similarity,
                    novelty_score=novelty,
                    filter_report=filter_report,
                )
            )
        return candidates

    def _benchmark(
        self,
        *,
        claims: list[ClaimClusterMatch],
        mechanisms: list[MechanismMatch],
        families: list[FamilyMatch],
        references: list[ReferencePeptide],
        candidates: list[CandidatePeptide],
        expected: PeptideBenchmarkExpectation | None,
    ) -> PeptideBenchmarkSummary:
        top_mechanisms = {item.mechanism for item in mechanisms[:3]}
        top_families = {item.family for item in families[:3]}
        descriptor_plausibility = (
            round(
                sum(1 for candidate in candidates if candidate.filter_report.passed)
                / len(candidates),
                3,
            )
            if candidates
            else 0.0
        )
        novelty_penalty = (
            round(
                sum(1.0 - candidate.novelty_score for candidate in candidates)
                / len(candidates),
                3,
            )
            if candidates
            else 0.0
        )
        market_neighborhood_recall = (
            round(
                sum(
                    1
                    for reference in references
                    if top_mechanisms.intersection(reference.mechanisms)
                )
                / len(references),
                3,
            )
            if references
            else 0.0
        )
        mechanism_match = market_neighborhood_recall
        family_match = (
            round(
                sum(1 for reference in references if reference.family in top_families)
                / len(references),
                3,
            )
            if references
            else 0.0
        )
        expectation_match = None
        notes: list[str] = []
        if expected is not None:
            expected_claims = set(expected.claim_clusters)
            expected_mechanisms = set(expected.mechanisms)
            expected_families = set(expected.families)
            actual_claims = {item.claim_cluster for item in claims}
            expectation_match = {
                "claim_clusters": self._set_recall(expected_claims, actual_claims),
                "mechanisms": self._set_recall(expected_mechanisms, top_mechanisms),
                "families": self._set_recall(expected_families, top_families),
            }
            notes.append(
                "Expectation-aware metrics were computed from the supplied benchmark labels."
            )
            if expected_mechanisms:
                mechanism_match = expectation_match["mechanisms"]
            if expected_families:
                family_match = expectation_match["families"]
        else:
            notes.append(
                "No external benchmark labels supplied; metrics reflect retrieval "
                "self-consistency."
            )
        return PeptideBenchmarkSummary(
            mechanism_match=round(mechanism_match, 3),
            family_match=round(family_match, 3),
            descriptor_plausibility=descriptor_plausibility,
            novelty_penalty=novelty_penalty,
            market_neighborhood_recall=market_neighborhood_recall,
            expectation_match=expectation_match,
            notes=notes,
        )

    def _warnings_for_request(
        self,
        request: PeptideResearchRequest,
        claims: list[ClaimClusterMatch],
        references: list[ReferencePeptide],
    ) -> list[str]:
        warnings: list[str] = []
        if request.application_area != "cosmetic":
            warnings.append(
                "The current reference library is cosmetic-heavy, so therapeutic "
                "prompts have weaker coverage."
            )
        if not any(claim.score >= 0.5 for claim in claims):
            warnings.append("Prompt-to-claim normalization is low confidence.")
        if references and references[0].retrieval_score < 0.8:
            warnings.append("Reference retrieval did not find a strong market-neighborhood match.")
        return warnings

    def _render_markdown(self, result: PeptideResearchResult) -> str:
        claim_lines = "\n".join(
            f"- `{claim.claim_cluster}` ({claim.score:.2f}): {claim.rationale}"
            for claim in result.normalized_claims
        )
        mechanism_lines = "\n".join(
            f"- `{mechanism.mechanism}` ({mechanism.score:.2f})"
            for mechanism in result.mechanism_rankings[:4]
        )
        family_lines = "\n".join(
            f"- `{family.family}` ({family.score:.2f})"
            for family in result.family_rankings[:3]
        )
        reference_lines = "\n".join(
            f"- `{reference.name}` / `{reference.family}` / score `{reference.retrieval_score:.2f}`"
            for reference in result.reference_peptides
        )
        candidate_lines = "\n".join(
            f"- `{candidate.sequence}` from `{candidate.derived_from_peptide_id}` "
            f"(novelty `{candidate.novelty_score:.2f}`)"
            for candidate in result.candidate_peptides
        )
        return (
            f"# Peptide research: {result.prompt}\n\n"
            f"## Claim normalization\n{claim_lines or '- none'}\n\n"
            f"## Mechanisms\n{mechanism_lines or '- none'}\n\n"
            f"## Families\n{family_lines or '- none'}\n\n"
            f"## Reference peptides\n{reference_lines or '- none'}\n\n"
            f"## Candidate peptides\n{candidate_lines or '- none'}\n\n"
            "## Benchmark\n"
            f"- mechanism_match: {result.benchmark.mechanism_match:.2f}\n"
            f"- family_match: {result.benchmark.family_match:.2f}\n"
            f"- descriptor_plausibility: {result.benchmark.descriptor_plausibility:.2f}\n"
            f"- novelty_penalty: {result.benchmark.novelty_penalty:.2f}\n"
            f"- market_neighborhood_recall: {result.benchmark.market_neighborhood_recall:.2f}\n"
        )

    def _describe_sequence(self, sequence: str) -> PeptideDescriptor:
        length = len(sequence)
        hydrophobic = sum(1 for residue in sequence if residue in _HYDROPHOBIC)
        aromatic = sum(1 for residue in sequence if residue in _AROMATIC)
        positive = sum(1 for residue in sequence if residue in _POSITIVE)
        negative = sum(1 for residue in sequence if residue in _NEGATIVE)
        return PeptideDescriptor(
            length=length,
            net_charge=positive - negative,
            hydrophobic_fraction=round(hydrophobic / length, 3) if length else 0.0,
            aromatic_fraction=round(aromatic / length, 3) if length else 0.0,
        )

    def _mutate_sequence(self, sequence: str) -> str | None:
        positions = range(max(0, len(sequence) // 2 - 1), len(sequence))
        for position in positions:
            residue = sequence[position]
            substitutions = _SUBSTITUTIONS.get(residue, ())
            for substitute in substitutions:
                if substitute != residue:
                    return f"{sequence[:position]}{substitute}{sequence[position + 1:]}"
        return None

    def _filter_candidate(
        self,
        descriptors: PeptideDescriptor,
        novelty_score: float,
    ) -> CandidateFilterReport:
        passed_filters: list[str] = []
        warnings: list[str] = []
        if 3 <= descriptors.length <= 12:
            passed_filters.append("length")
        else:
            warnings.append("length_out_of_cosmetic_range")
        if -1 <= descriptors.net_charge <= 3:
            passed_filters.append("net_charge")
        else:
            warnings.append("charge_may_complicate_delivery")
        if 0.2 <= descriptors.hydrophobic_fraction <= 0.7:
            passed_filters.append("hydrophobic_fraction")
        else:
            warnings.append("hydrophobicity_outside_reference_band")
        if novelty_score >= 0.15:
            passed_filters.append("novelty")
        else:
            warnings.append("too_close_to_reference")
        return CandidateFilterReport(
            passed=len(warnings) == 0,
            passed_filters=passed_filters,
            warnings=warnings,
        )

    def _sequence_similarity(self, reference: str, candidate: str) -> float:
        shared_positions = sum(
            1 for left, right in zip(reference, candidate, strict=False) if left == right
        )
        return shared_positions / max(len(reference), len(candidate))

    def _set_recall(self, expected: Iterable[str], actual: Iterable[str]) -> float:
        expected_set = set(expected)
        if not expected_set:
            return 0.0
        actual_set = set(actual)
        return round(len(expected_set.intersection(actual_set)) / len(expected_set), 3)
