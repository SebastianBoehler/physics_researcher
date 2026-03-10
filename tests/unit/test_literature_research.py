from __future__ import annotations

from autolab.agents import (
    LiteraturePaperInput,
    LiteratureResearchRequest,
    LiteratureResearchService,
    detect_research_mode,
)
from autolab.agents.arxiv import parse_arxiv_feed
from autolab.agents.literature_models import AuthorRecord, PaperRecord
from autolab.core.enums import ResearchMode
from autolab.core.settings import get_settings


class StubArxivClient:
    def __init__(self, papers: list[PaperRecord]) -> None:
        self._papers = papers

    def resolve_inputs(self, papers: list[LiteraturePaperInput]) -> list[PaperRecord]:
        return [paper.model_copy(deep=True) for paper in self._papers]


def test_detect_research_mode_from_arxiv_and_phrase_inputs() -> None:
    url_request = LiteratureResearchRequest(
        topic="Condensed matter transport",
        papers=[LiteraturePaperInput(url="https://arxiv.org/abs/2401.12345")],
    )
    phrase_request = LiteratureResearchRequest(
        topic="Compare papers on photonic crystals",
        papers=[LiteraturePaperInput(title="Photonic crystal benchmark")],
        notes="Please review the literature and find research gaps.",
    )

    assert detect_research_mode(url_request) == ResearchMode.LITERATURE_RESEARCH
    assert detect_research_mode(phrase_request) == ResearchMode.LITERATURE_RESEARCH


def test_parse_arxiv_feed_extracts_metadata() -> None:
    feed = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.12345v1</id>
        <updated>2026-01-02T00:00:00Z</updated>
        <published>2026-01-01T00:00:00Z</published>
        <title>Quantum Sensor Stability</title>
        <summary>This paper shows quantum sensor stability improves measurement accuracy.</summary>
        <author><name>Alice Example</name></author>
        <author><name>Bob Example</name></author>
        <link href="http://arxiv.org/abs/2401.12345v1" rel="alternate" type="text/html" />
        <link
          title="pdf"
          href="http://arxiv.org/pdf/2401.12345v1"
          rel="related"
          type="application/pdf"
        />
        <category term="quant-ph" />
      </entry>
    </feed>
    """

    papers = parse_arxiv_feed(feed)

    assert len(papers) == 1
    assert papers[0].arxiv_id == "2401.12345v1"
    assert papers[0].authors[0].name == "Alice Example"
    assert papers[0].year == 2026
    assert papers[0].categories == ["quant-ph"]


def test_literature_service_handles_duplicates_and_contradictions() -> None:
    settings = get_settings()
    papers = [
        PaperRecord(
            paper_id="2401.12345",
            arxiv_id="2401.12345",
            title="Quantum Sensor Stability",
            abstract=(
                "This study shows quantum sensor stability improves accuracy "
                "under cryogenic operation."
            ),
            authors=[AuthorRecord(name="Alice Example")],
            year=2024,
        ),
        PaperRecord(
            paper_id="2401.12345",
            arxiv_id="2401.12345",
            title="Quantum Sensor Stability",
            abstract=(
                "This study shows quantum sensor stability improves accuracy "
                "under cryogenic operation."
            ),
            authors=[AuthorRecord(name="Alice Example")],
            year=2024,
        ),
        PaperRecord(
            paper_id="2402.54321",
            arxiv_id="2402.54321",
            title="Quantum Sensor Stability Limits",
            abstract=(
                "This study shows quantum sensor stability decreases accuracy "
                "under cryogenic operation."
            ),
            authors=[AuthorRecord(name="Bob Example")],
            year=2025,
        ),
    ]
    service = LiteratureResearchService(settings, arxiv_client=StubArxivClient(papers))

    result = service.run(
        LiteratureResearchRequest(
            topic="Quantum sensor stability",
            papers=[
                LiteraturePaperInput(arxiv_id="2401.12345"),
                LiteraturePaperInput(arxiv_id="2401.12345"),
                LiteraturePaperInput(arxiv_id="2402.54321"),
            ],
        )
    )

    assert len(result.papers) == 2
    assert any("duplicate_reference" in paper.flags for paper in result.papers)
    assert result.contradictions
    assert result.stage_status[0].stage == "intake_protocol"
    assert result.stage_status[-1].stage == "so_what_test"


def test_literature_service_marks_single_paper_limited_confidence() -> None:
    settings = get_settings()
    service = LiteratureResearchService(
        settings,
        arxiv_client=StubArxivClient(
            [
                PaperRecord(
                    paper_id="single-paper",
                    title="Photonic Crystal Benchmark",
                    abstract=(
                        "This experiment improves photonic crystal transmission in a narrow regime."
                    ),
                    authors=[AuthorRecord(name="Casey Example")],
                    year=2025,
                )
            ]
        ),
    )

    result = service.run(
        LiteratureResearchRequest(
            topic="Photonic crystals",
            papers=[LiteraturePaperInput(title="Photonic Crystal Benchmark")],
        )
    )

    assert result.intake.limited_confidence is True
    assert "Single-paper evidence suggests" in result.synthesis.collective_beliefs[0]
    assert result.markdown_rendering is not None


def test_literature_service_marks_stage_degraded_and_continues() -> None:
    settings = get_settings()
    service = LiteratureResearchService(
        settings,
        arxiv_client=StubArxivClient(
            [
                PaperRecord(
                    paper_id="2401.10001",
                    title="Transport in layered materials",
                    abstract="This simulation improves transport estimates for layered materials.",
                    authors=[AuthorRecord(name="Dana Example")],
                    year=2024,
                ),
                PaperRecord(
                    paper_id="2401.10002",
                    title="Transport in layered materials under noise",
                    abstract=(
                        "This simulation lowers transport estimates for layered "
                        "materials under noise."
                    ),
                    authors=[AuthorRecord(name="Evan Example")],
                    year=2025,
                ),
            ]
        ),
    )

    service._build_contradictions = lambda papers: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[method-assign]

    result = service.run(
        LiteratureResearchRequest(
            topic="Layered-material transport",
            papers=[
                LiteraturePaperInput(arxiv_id="2401.10001"),
                LiteraturePaperInput(arxiv_id="2401.10002"),
            ],
        )
    )

    contradiction_status = next(
        item for item in result.stage_status if item.stage == "contradiction_finder"
    )
    assert contradiction_status.status == "degraded"
    assert result.knowledge_map.central_claim
    assert result.errors
