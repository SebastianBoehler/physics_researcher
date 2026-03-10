from __future__ import annotations

from uuid import uuid4

import httpx
from autolab.agents import (
    LiteratureResearchRequest,
    LiteratureResearchResult,
    LiteratureResearchService,
)
from autolab.agents.literature_models import (
    FieldSynthesis,
    IntakeResult,
    KnowledgeMap,
    MethodologyAudit,
    PaperRecord,
    SoWhatSummary,
)
from autolab.api.dependencies import get_literature_research_service
from autolab.api.main import app
from autolab.cli.main import app as cli_app
from autolab.core.settings import get_settings
from fastapi.testclient import TestClient
from typer.testing import CliRunner


class StubLiteratureService(LiteratureResearchService):
    def __init__(self) -> None:
        self.requests: list[LiteratureResearchRequest] = []

    def run(self, request: LiteratureResearchRequest) -> LiteratureResearchResult:
        self.requests.append(request)
        return LiteratureResearchResult(
            topic=request.topic,
            papers=[
                PaperRecord(
                    paper_id="2401.12345",
                    arxiv_id="2401.12345",
                    title="Quantum Sensor Stability",
                    abstract="This study shows quantum sensor stability improves accuracy.",
                    year=2024,
                )
            ],
            intake=IntakeResult(),
            contradictions=[],
            citation_chains=[],
            gaps=[],
            methodology_audit=MethodologyAudit(),
            synthesis=FieldSynthesis(
                collective_beliefs=["Quantum sensor stability improves accuracy."],
                contested_questions=[],
                shared_assumptions=[],
                promising_next_steps=[],
                evidence_note="stub",
            ),
            assumptions=[],
            knowledge_map=KnowledgeMap(
                central_claim="Quantum sensor stability improves accuracy.",
                supporting_pillars=["Improved low-noise performance."],
                contested_zones=[],
                frontier_questions=[],
            ),
            so_what=SoWhatSummary(
                proven="Quantum sensor stability improves accuracy.",
                unknown="Broader generalization is not yet known.",
                matters="Sensor design choices depend on this result.",
            ),
            stage_status=[],
            errors=[],
            markdown_rendering="# Stub output",
        )


def test_literature_research_endpoint_returns_structured_result() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}
    stub_service = StubLiteratureService()
    app.dependency_overrides[get_literature_research_service] = lambda: stub_service

    response = client.post(
        "/literature-research",
        json={
            "topic": "Quantum sensor stability",
            "papers": [{"arxiv_id": "2401.12345"}],
            "include_markdown": True,
        },
        headers=headers,
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["mode"] == "literature_research"
    assert payload["topic"] == "Quantum sensor stability"
    assert stub_service.requests[0].papers[0].arxiv_id == "2401.12345"


def test_research_literature_cli_posts_expected_payload(monkeypatch) -> None:
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
            json={
                "result": {
                    "mode": "literature_research",
                    "topic": json["topic"],
                    "id": str(uuid4()),
                }
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = runner.invoke(
        cli_app,
        [
            "research-literature",
            "Quantum sensor stability",
            "--paper",
            "2401.12345",
            "--paper",
            "https://arxiv.org/abs/2402.54321",
            "--notes",
            "review the literature",
        ],
    )

    assert result.exit_code == 0
    assert (
        captured["url"]
        == f"http://{get_settings().app.api_host}:{get_settings().app.api_port}/literature-research"
    )
    assert captured["json"] == {
        "topic": "Quantum sensor stability",
        "papers": [{"arxiv_id": "2401.12345"}, {"url": "https://arxiv.org/abs/2402.54321"}],
        "notes": "review the literature",
        "include_markdown": True,
    }
