from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from xml.etree import ElementTree

import httpx
from autolab.agents.literature_models import (
    AuthorRecord,
    LiteraturePaperInput,
    PaperRecord,
)
from autolab.core.settings import Settings

_ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}
_ARXIV_NAMESPACE = {"arxiv": "http://arxiv.org/schemas/atom"}


class ArxivClientProtocol(Protocol):
    def resolve_inputs(self, papers: Sequence[LiteraturePaperInput]) -> list[PaperRecord]: ...


def extract_arxiv_id(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    for prefix in ("https://arxiv.org/abs/", "http://arxiv.org/abs/"):
        if cleaned.startswith(prefix):
            return cleaned.removeprefix(prefix).split("?")[0].strip("/")
    for prefix in ("https://arxiv.org/pdf/", "http://arxiv.org/pdf/"):
        if cleaned.startswith(prefix):
            return cleaned.removeprefix(prefix).split("?")[0].removesuffix(".pdf").strip("/")
    if cleaned.lower().startswith("arxiv:"):
        return cleaned[6:]
    if "/" in cleaned or "." in cleaned:
        return cleaned
    return None


def parse_arxiv_feed(xml_payload: str) -> list[PaperRecord]:
    root = ElementTree.fromstring(xml_payload)
    papers: list[PaperRecord] = []
    for entry in root.findall("atom:entry", _ATOM_NAMESPACE):
        paper_url = entry.findtext("atom:id", default="", namespaces=_ATOM_NAMESPACE).strip()
        title = _clean_text(entry.findtext("atom:title", default="", namespaces=_ATOM_NAMESPACE))
        abstract = _clean_text(
            entry.findtext("atom:summary", default="", namespaces=_ATOM_NAMESPACE)
        )
        authors: list[AuthorRecord] = []
        for author in entry.findall("atom:author", _ATOM_NAMESPACE):
            author_name = _clean_text(
                author.findtext("atom:name", default="", namespaces=_ATOM_NAMESPACE)
            )
            if author_name:
                authors.append(AuthorRecord(name=author_name))
        categories = [
            category.attrib["term"]
            for category in entry.findall("atom:category", _ATOM_NAMESPACE)
            if category.attrib.get("term")
        ]
        published_text = entry.findtext("atom:published", default="", namespaces=_ATOM_NAMESPACE)
        year = None
        if published_text:
            year = datetime.fromisoformat(published_text.replace("Z", "+00:00")).year
        pdf_url = None
        for link in entry.findall("atom:link", _ATOM_NAMESPACE):
            href = link.attrib.get("href")
            title_attr = link.attrib.get("title", "")
            if href and title_attr == "pdf":
                pdf_url = href
                break
        raw_id = entry.findtext("atom:id", default="", namespaces=_ATOM_NAMESPACE)
        arxiv_id = extract_arxiv_id(raw_id) or entry.findtext(
            "arxiv:doi", default="", namespaces=_ARXIV_NAMESPACE
        )
        paper_id = arxiv_id or _paper_id_from_title(title)
        papers.append(
            PaperRecord(
                paper_id=paper_id,
                arxiv_id=arxiv_id,
                title=title or "Untitled arXiv paper",
                abstract=abstract,
                authors=authors,
                year=year,
                url=paper_url or None,
                pdf_url=pdf_url,
                categories=categories,
                metadata_quality="complete" if title and abstract and authors else "partial",
            )
        )
    return papers


class ArxivClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            follow_redirects=True,
            timeout=settings.literature.timeout_seconds,
            headers={"User-Agent": settings.literature.user_agent},
        )
        self._owns_client = client is None

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        if self._owns_client:
            self._client.close()

    def resolve_inputs(self, papers: Sequence[LiteraturePaperInput]) -> list[PaperRecord]:
        resolved: list[PaperRecord] = []
        for paper in papers:
            candidate = self._resolve_single(paper)
            if candidate is not None:
                resolved.append(candidate)
        return resolved

    def _resolve_single(self, paper: LiteraturePaperInput) -> PaperRecord | None:
        arxiv_id = None
        if paper.arxiv_id:
            arxiv_id = extract_arxiv_id(paper.arxiv_id)
        if arxiv_id is None and paper.url:
            arxiv_id = extract_arxiv_id(paper.url)
        fetched = None
        if arxiv_id is not None:
            fetched = self._fetch_by_id(arxiv_id)
        elif paper.title and not paper.abstract:
            fetched = self._search_by_title(paper.title)
        if fetched is None and not any((paper.title, paper.abstract, paper.notes)):
            return None
        merged = fetched or PaperRecord(
            paper_id=_paper_id_from_title(
                paper.title or paper.arxiv_id or paper.url or "manual-paper"
            ),
            arxiv_id=arxiv_id,
            title=paper.title or arxiv_id or "Untitled literature input",
            abstract=paper.abstract or "",
            url=paper.url,
            metadata_quality="partial",
            flags=["manual_only"],
        )
        if paper.title:
            merged.title = paper.title
        if paper.abstract:
            merged.abstract = paper.abstract
        if paper.url:
            merged.url = paper.url
        if paper.notes:
            merged.notes = paper.notes if not merged.notes else f"{merged.notes}\n{paper.notes}"
        if paper.arxiv_id and merged.arxiv_id is None:
            merged.arxiv_id = extract_arxiv_id(paper.arxiv_id)
        if not merged.abstract:
            merged.flags.append("missing_abstract")
            merged.metadata_quality = "partial"
        return merged

    def _fetch_by_id(self, arxiv_id: str) -> PaperRecord | None:
        response = self._client.get(
            self._settings.literature.arxiv_api_url,
            params={"id_list": arxiv_id},
        )
        response.raise_for_status()
        parsed = parse_arxiv_feed(response.text)
        return parsed[0] if parsed else None

    def _search_by_title(self, title: str) -> PaperRecord | None:
        response = self._client.get(
            self._settings.literature.arxiv_api_url,
            params={
                "search_query": f'ti:"{title}"',
                "start": 0,
                "max_results": self._settings.literature.max_results_per_query,
            },
        )
        response.raise_for_status()
        parsed = parse_arxiv_feed(response.text)
        if not parsed:
            return None
        normalized_title = _normalize_title(title)
        exact = next(
            (paper for paper in parsed if _normalize_title(paper.title) == normalized_title),
            None,
        )
        return exact or parsed[0]


def _paper_id_from_title(value: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else "-" for character in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "paper"


def _normalize_title(value: str) -> str:
    return " ".join(_clean_text(value).lower().split())


def _clean_text(value: str) -> str:
    return " ".join(value.split())
