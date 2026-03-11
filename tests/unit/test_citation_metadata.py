from __future__ import annotations

import json

import httpx
from autolab.agents.citation_metadata import CitationMetadataResolver
from autolab.core.settings import get_settings


def test_citation_metadata_resolver_parses_crossref_doi() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.crossref.org/works/10.1000/example")
        return httpx.Response(
            200,
            json={
                "message": {
                    "title": ["Example DOI Paper"],
                    "container-title": ["Journal of Testing"],
                    "issued": {"date-parts": [[2024, 1, 1]]},
                    "URL": "https://doi.org/10.1000/example",
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    resolver = CitationMetadataResolver(get_settings(), client=client)

    metadata = resolver.resolve(doi="10.1000/example")

    assert metadata.title == "Example DOI Paper"
    assert metadata.year == 2024
    assert metadata.journal == "Journal of Testing"


def test_citation_metadata_resolver_parses_pubmed_pmid() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/esummary.fcgi")
        payload = {
            "result": {
                "uids": ["12345678"],
                "12345678": {
                    "title": "Example PMID Paper",
                    "fulljournalname": "PubMed Journal",
                    "pubdate": "2023 Jan",
                    "articleids": [
                        {"idtype": "pubmed", "value": "12345678"},
                        {"idtype": "doi", "value": "10.2000/example"},
                    ],
                },
            }
        }
        return httpx.Response(200, content=json.dumps(payload))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    resolver = CitationMetadataResolver(get_settings(), client=client)

    metadata = resolver.resolve(pmid="12345678")

    assert metadata.title == "Example PMID Paper"
    assert metadata.year == 2023
    assert metadata.journal == "PubMed Journal"
    assert metadata.doi == "10.2000/example"
    assert metadata.url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"


def test_citation_metadata_resolver_retries_after_rate_limit(monkeypatch) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={
                "result": {
                    "uids": ["12345678"],
                    "12345678": {
                        "title": "Recovered PMID Paper",
                        "fulljournalname": "PubMed Journal",
                        "pubdate": "2023 Jan",
                        "articleids": [{"idtype": "pubmed", "value": "12345678"}],
                    },
                }
            },
        )

    monkeypatch.setattr("autolab.agents.citation_metadata.time.sleep", lambda _: None)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    resolver = CitationMetadataResolver(get_settings(), client=client)

    metadata = resolver.resolve(pmid="12345678")

    assert calls["count"] == 2
    assert metadata.title == "Recovered PMID Paper"
