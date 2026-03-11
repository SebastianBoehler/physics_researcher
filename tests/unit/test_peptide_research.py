from __future__ import annotations

from autolab.agents import (
    PeptideBenchmarkExpectation,
    PeptideResearchRequest,
    PeptideResearchService,
    detect_peptide_research_mode,
)
from autolab.agents.peptide_reference_data import load_reference_dataset
from autolab.core.enums import ResearchMode
from autolab.core.settings import get_settings


def test_detect_peptide_research_mode_from_prompt_keywords() -> None:
    request = PeptideResearchRequest(
        prompt="Need a peptide idea for fewer wrinkles and firmer skin"
    )

    assert detect_peptide_research_mode(request) == ResearchMode.PEPTIDE_RESEARCH


def test_peptide_reference_dataset_is_versioned_and_cited() -> None:
    dataset = load_reference_dataset()

    assert dataset.dataset_id == "cosmetic-peptide-market-neighborhoods"
    assert dataset.version == "1.1.0"
    assert dataset.entries[0].evidence.citations
    assert dataset.entries[0].evidence.citations[0].url.startswith("https://pubmed.ncbi.nlm.nih.gov/")


def test_peptide_research_service_maps_wrinkles_to_neuromodulatory_family() -> None:
    service = PeptideResearchService(get_settings())

    result = service.run(
        PeptideResearchRequest(
            prompt="fewer wrinkles around the eyes",
            benchmark=PeptideBenchmarkExpectation(
                claim_clusters=["fewer_wrinkles"],
                mechanisms=["cosmetic_neuromodulation"],
                families=["neuromodulatory_cosmetic_peptide"],
            ),
        )
    )

    assert result.normalized_claims[0].claim_cluster == "fewer_wrinkles"
    assert result.mechanism_rankings[0].mechanism == "cosmetic_neuromodulation"
    assert "neuromodulatory_cosmetic_peptide" in {
        family.family for family in result.family_rankings[:3]
    }
    assert "acetyl-hexapeptide-8" in {
        peptide.peptide_id for peptide in result.reference_peptides
    }
    assert result.reference_peptides[0].evidence.citations
    assert result.metadata["dataset_version"] == "1.1.0"
    assert result.benchmark.expectation_match == {
        "claim_clusters": 1.0,
        "mechanisms": 1.0,
        "families": 1.0,
    }


def test_peptide_research_service_generates_filtered_candidates() -> None:
    service = PeptideResearchService(get_settings())

    result = service.run(
        PeptideResearchRequest(
            prompt="barrier repair for stressed skin",
            max_candidates=2,
        )
    )

    assert len(result.candidate_peptides) == 2
    assert result.candidate_peptides[0].filter_report.passed_filters
    assert result.benchmark.market_neighborhood_recall > 0.0
