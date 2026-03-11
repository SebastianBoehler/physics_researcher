from __future__ import annotations

import re
import time
from typing import Protocol

import httpx
from autolab.core.models import AutolabModel
from autolab.core.settings import Settings

_YEAR_PATTERN = re.compile(r"(19|20)\d{2}")


class CitationMetadata(AutolabModel):
    title: str
    year: int
    journal: str
    url: str
    doi: str | None = None
    pmid: str | None = None


class CitationMetadataResolverProtocol(Protocol):
    def resolve(self, *, doi: str | None = None, pmid: str | None = None) -> CitationMetadata: ...


class CitationMetadataResolver:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            follow_redirects=True,
            timeout=settings.literature.timeout_seconds,
            headers={
                "User-Agent": settings.literature.user_agent,
                "Accept": "application/json",
            },
        )
        self._owns_client = client is None

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        if self._owns_client:
            self._client.close()

    def resolve(self, *, doi: str | None = None, pmid: str | None = None) -> CitationMetadata:
        if doi:
            return self._resolve_doi(doi)
        if pmid:
            return self._resolve_pmid(pmid)
        msg = "citation resolution requires a DOI or PMID"
        raise ValueError(msg)

    def _resolve_doi(self, doi: str) -> CitationMetadata:
        response = self._get_with_retry(f"https://api.crossref.org/works/{doi}")
        response.raise_for_status()
        payload = response.json()["message"]
        title = _first_text(payload.get("title")) or doi
        journal = _first_text(payload.get("container-title")) or "Unknown journal"
        year = _extract_crossref_year(payload)
        url = payload.get("URL") or f"https://doi.org/{doi}"
        return CitationMetadata(
            title=title,
            year=year,
            journal=journal,
            url=url,
            doi=doi,
        )

    def _resolve_pmid(self, pmid: str) -> CitationMetadata:
        response = self._get_with_retry(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": pmid, "retmode": "json"},
        )
        response.raise_for_status()
        payload = response.json()["result"][str(pmid)]
        title = payload.get("title") or f"PMID {pmid}"
        journal = payload.get("fulljournalname") or payload.get("source") or "PubMed"
        year = _extract_year_from_text(payload.get("pubdate", ""))
        article_ids = payload.get("articleids", [])
        doi = next(
            (item.get("value") for item in article_ids if item.get("idtype") == "doi"),
            None,
        )
        return CitationMetadata(
            title=title,
            year=year,
            journal=journal,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            doi=doi,
            pmid=str(pmid),
        )

    def _get_with_retry(
        self, url: str, *, params: dict[str, str] | None = None, max_attempts: int = 3
    ) -> httpx.Response:
        for attempt in range(1, max_attempts + 1):
            response = self._client.get(url, params=params)
            if response.status_code != httpx.codes.TOO_MANY_REQUESTS:
                return response
            retry_after = response.headers.get("Retry-After")
            sleep_seconds = float(retry_after) if retry_after else 1.5 * attempt
            if attempt == max_attempts:
                return response
            time.sleep(sleep_seconds)
        msg = "unreachable retry loop"
        raise RuntimeError(msg)


def _first_text(value: object) -> str | None:
    if isinstance(value, list) and value:
        item = value[0]
        return str(item).strip() if item else None
    if isinstance(value, str):
        return value.strip() or None
    return None


def _extract_crossref_year(payload: dict[str, object]) -> int:
    for key in ("issued", "published-print", "published-online", "created"):
        value = payload.get(key)
        if isinstance(value, dict):
            date_parts = value.get("date-parts")
            if (
                isinstance(date_parts, list)
                and date_parts
                and isinstance(date_parts[0], list)
                and date_parts[0]
            ):
                first = date_parts[0][0]
                if isinstance(first, int):
                    return first
    msg = "unable to extract publication year from Crossref payload"
    raise ValueError(msg)


def _extract_year_from_text(value: str) -> int:
    match = _YEAR_PATTERN.search(value)
    if match is None:
        msg = f"unable to extract publication year from {value!r}"
        raise ValueError(msg)
    return int(match.group(0))
