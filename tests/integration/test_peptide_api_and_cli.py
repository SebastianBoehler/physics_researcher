from __future__ import annotations

import httpx
from autolab.agents import PeptideResearchRequest, PeptideResearchResult, PeptideResearchService
from autolab.agents.peptide_models import (
    CandidateFilterReport,
    CandidatePeptide,
    ClaimClusterMatch,
    FamilyMatch,
    MechanismMatch,
    PeptideBenchmarkSummary,
    PeptideDescriptor,
    ReferencePeptide,
)
from autolab.api.dependencies import get_peptide_research_service
from autolab.api.main import app
from autolab.cli.main import app as cli_app
from autolab.core.settings import get_settings
from fastapi.testclient import TestClient
from typer.testing import CliRunner


class StubPeptideService(PeptideResearchService):
    def __init__(self) -> None:
        self.requests: list[PeptideResearchRequest] = []

    def run(self, request: PeptideResearchRequest) -> PeptideResearchResult:
        self.requests.append(request)
        descriptor = PeptideDescriptor(
            length=6,
            net_charge=0,
            hydrophobic_fraction=0.333,
            aromatic_fraction=0.0,
        )
        return PeptideResearchResult(
            prompt=request.prompt,
            application_area=request.application_area,
            normalized_claims=[
                ClaimClusterMatch(
                    claim_cluster="fewer_wrinkles",
                    score=0.92,
                    matched_terms=["wrinkles"],
                    rationale="stub",
                )
            ],
            mechanism_rankings=[
                MechanismMatch(
                    mechanism="cosmetic_neuromodulation",
                    score=0.96,
                    supporting_claim_clusters=["fewer_wrinkles"],
                    rationale="stub",
                )
            ],
            family_rankings=[
                FamilyMatch(
                    family="neuromodulatory_cosmetic_peptide",
                    score=0.94,
                    supporting_mechanisms=["cosmetic_neuromodulation"],
                    supporting_peptide_ids=["acetyl-hexapeptide-8"],
                    rationale="stub",
                )
            ],
            reference_peptides=[
                ReferencePeptide(
                    peptide_id="acetyl-hexapeptide-8",
                    name="Acetyl Hexapeptide-8",
                    sequence="EEMQRR",
                    family="neuromodulatory_cosmetic_peptide",
                    claim_clusters=["fewer_wrinkles"],
                    mechanisms=["cosmetic_neuromodulation"],
                    modifications=["acetylated", "amidated"],
                    aliases=["Argireline"],
                    evidence_level="marketed",
                    rationale="stub",
                    descriptors=descriptor,
                    retrieval_score=0.96,
                )
            ],
            candidate_peptides=[
                CandidatePeptide(
                    candidate_id="cand-1",
                    sequence="EEMQRK",
                    family="neuromodulatory_cosmetic_peptide",
                    derived_from_peptide_id="acetyl-hexapeptide-8",
                    modifications=["acetylated", "amidated"],
                    rationale="stub",
                    descriptors=descriptor,
                    similarity_to_reference=0.833,
                    novelty_score=0.167,
                    filter_report=CandidateFilterReport(
                        passed=True,
                        passed_filters=["length", "net_charge", "hydrophobic_fraction", "novelty"],
                        warnings=[],
                    ),
                )
            ],
            benchmark=PeptideBenchmarkSummary(
                mechanism_match=1.0,
                family_match=1.0,
                descriptor_plausibility=1.0,
                novelty_penalty=0.833,
                market_neighborhood_recall=1.0,
                expectation_match={"claim_clusters": 1.0, "mechanisms": 1.0, "families": 1.0},
                notes=["stub"],
            ),
            warnings=[],
            metadata={"source": "stub"},
            markdown_rendering="# Stub peptide output",
        )


def test_peptide_research_endpoint_returns_structured_result() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}
    stub_service = StubPeptideService()
    app.dependency_overrides[get_peptide_research_service] = lambda: stub_service

    response = client.post(
        "/peptide-research",
        json={
            "prompt": "fewer wrinkles around the eyes",
            "benchmark": {
                "claim_clusters": ["fewer_wrinkles"],
                "mechanisms": ["cosmetic_neuromodulation"],
                "families": ["neuromodulatory_cosmetic_peptide"],
            },
        },
        headers=headers,
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["mode"] == "peptide_research"
    assert payload["prompt"] == "fewer wrinkles around the eyes"
    assert stub_service.requests[0].benchmark is not None


def test_research_peptides_cli_posts_expected_payload(monkeypatch) -> None:
    runner = CliRunner()
    captured: dict[str, object] = {}

    def fake_post(
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        captured["url"] = url
        captured["json"] = json
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={"result": {"mode": "peptide_research", "prompt": json["prompt"]}},
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = runner.invoke(
        cli_app,
        [
            "research-peptides",
            "fewer wrinkles around the eyes",
            "--notes",
            "target expression lines",
            "--expected-claim-cluster",
            "fewer_wrinkles",
            "--expected-mechanism",
            "cosmetic_neuromodulation",
            "--expected-family",
            "neuromodulatory_cosmetic_peptide",
        ],
    )

    assert result.exit_code == 0
    assert (
        captured["url"]
        == f"http://{get_settings().app.api_host}:{get_settings().app.api_port}/peptide-research"
    )
    assert captured["json"] == {
        "prompt": "fewer wrinkles around the eyes",
        "notes": "target expression lines",
        "application_area": "cosmetic",
        "max_reference_peptides": 5,
        "max_candidates": 3,
        "benchmark": {
            "claim_clusters": ["fewer_wrinkles"],
            "mechanisms": ["cosmetic_neuromodulation"],
            "families": ["neuromodulatory_cosmetic_peptide"],
        },
        "include_markdown": True,
    }
