from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from autolab.agents.citation_metadata import CitationMetadata, CitationMetadataResolverProtocol
from autolab.agents.peptide_models import (
    PeptideCitation,
    PeptideEvidence,
    PeptideReferenceDataset,
    PeptideReferenceRecord,
)
from autolab.core.models import AutolabModel
from pydantic import Field


class CitationSeed(AutolabModel):
    doi: str | None = None
    pmid: str | None = None
    title: str | None = None
    year: int | None = None
    journal: str | None = None
    url: str | None = None
    evidence_type: str = "review"
    supports: list[str] = Field(default_factory=list)


class PeptideReferenceSeed(AutolabModel):
    peptide_id: str
    name: str
    sequence: str
    family: str
    claim_clusters: list[str] = Field(default_factory=list)
    mechanisms: list[str] = Field(default_factory=list)
    modifications: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    evidence_level: str = "marketed"
    rationale: str
    evidence_tier: str = "unrated"
    evidence_summary: str = ""
    evidence_caveats: list[str] = Field(default_factory=list)
    citations: list[CitationSeed] = Field(default_factory=list)


class DatasetBuilderProtocol(Protocol):
    def build_dataset(
        self, *, seeds: Sequence[PeptideReferenceSeed], version: str
    ) -> PeptideReferenceDataset: ...


class PeptideReferenceDatasetBuilder:
    def __init__(self, resolver: CitationMetadataResolverProtocol | None = None) -> None:
        self._resolver = resolver

    def load_seed_records(self, paths: Sequence[Path]) -> list[PeptideReferenceSeed]:
        records: list[PeptideReferenceSeed] = []
        for path in paths:
            if path.suffix.lower() == ".csv":
                records.extend(self._load_csv(path))
            elif path.suffix.lower() in {".jsonl", ".ndjson"}:
                records.extend(self._load_jsonl(path))
            else:
                msg = f"unsupported seed format: {path}"
                raise ValueError(msg)
        return records

    def build_dataset(
        self,
        *,
        seeds: Sequence[PeptideReferenceSeed],
        dataset_id: str,
        version: str,
        scope: str,
        description: str,
        generated_on: str | None = None,
    ) -> PeptideReferenceDataset:
        return PeptideReferenceDataset(
            dataset_id=dataset_id,
            version=version,
            scope=scope,
            generated_on=generated_on or datetime.now(UTC).date().isoformat(),
            description=description,
            entries=[self._build_record(seed) for seed in seeds],
        )

    def write_dataset(self, dataset: PeptideReferenceDataset, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(dataset.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )

    def _build_record(self, seed: PeptideReferenceSeed) -> PeptideReferenceRecord:
        return PeptideReferenceRecord(
            peptide_id=seed.peptide_id,
            name=seed.name,
            sequence=seed.sequence,
            family=seed.family,
            claim_clusters=seed.claim_clusters,
            mechanisms=seed.mechanisms,
            modifications=seed.modifications,
            aliases=seed.aliases,
            evidence_level=seed.evidence_level,
            rationale=seed.rationale,
            evidence=PeptideEvidence(
                tier=seed.evidence_tier,
                summary=seed.evidence_summary,
                citations=self._build_citations(seed.citations),
                caveats=seed.evidence_caveats,
            ),
        )

    def _build_citations(self, citations: Sequence[CitationSeed]) -> list[PeptideCitation]:
        built: list[PeptideCitation] = []
        seen_ids: set[str] = set()
        for citation in citations:
            metadata = self._resolve_metadata(citation)
            citation_id = _citation_id(citation, metadata)
            if citation_id in seen_ids:
                continue
            seen_ids.add(citation_id)
            built.append(
                PeptideCitation(
                    citation_id=citation_id,
                    title=citation.title or metadata.title,
                    year=citation.year or metadata.year,
                    journal=citation.journal or metadata.journal,
                    url=citation.url or metadata.url,
                    doi=citation.doi or metadata.doi,
                    pmid=citation.pmid or metadata.pmid,
                    evidence_type=citation.evidence_type,
                    supports=citation.supports,
                )
            )
        return built

    def _resolve_metadata(self, citation: CitationSeed) -> CitationMetadata:
        if all((citation.title, citation.year, citation.journal, citation.url)):
            return CitationMetadata(
                title=citation.title,
                year=citation.year,
                journal=citation.journal,
                url=citation.url,
                doi=citation.doi,
                pmid=citation.pmid,
            )
        if self._resolver is None:
            msg = (
                "citation metadata is incomplete and no resolver was provided "
                f"for citation seed {citation.model_dump(mode='json')}"
            )
            raise ValueError(msg)
        return self._resolver.resolve(doi=citation.doi, pmid=citation.pmid)

    def _load_csv(self, path: Path) -> list[PeptideReferenceSeed]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [
                PeptideReferenceSeed.model_validate(_normalize_seed_payload(row))
                for row in reader
            ]

    def _load_jsonl(self, path: Path) -> list[PeptideReferenceSeed]:
        records: list[PeptideReferenceSeed] = []
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                records.append(
                    PeptideReferenceSeed.model_validate(_normalize_seed_payload(json.loads(line)))
                )
        return records


def update_dataset_manifest(
    *,
    manifest_path: Path,
    dataset: PeptideReferenceDataset,
    filename: str,
    set_default: bool,
) -> None:
    payload: dict[str, Any]
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        payload = {"default_version": dataset.version, "datasets": []}
    datasets = [
        item for item in payload.get("datasets", []) if item.get("version") != dataset.version
    ]
    datasets.append(
        {
            "version": dataset.version,
            "filename": filename,
            "dataset_id": dataset.dataset_id,
            "scope": dataset.scope,
            "description": dataset.description,
        }
    )
    datasets.sort(key=lambda item: item["version"])
    payload["datasets"] = datasets
    if set_default:
        payload["default_version"] = dataset.version
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _normalize_seed_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    for key in (
        "claim_clusters",
        "mechanisms",
        "modifications",
        "aliases",
        "evidence_caveats",
    ):
        normalized[key] = _normalize_list(normalized.get(key))
    normalized["citations"] = _normalize_citations(normalized.get("citations"))
    return normalized


def _normalize_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            parsed = json.loads(stripped)
            return [str(item) for item in parsed]
        return [part.strip() for part in stripped.split("|") if part.strip()]
    msg = f"unsupported list value: {value!r}"
    raise ValueError(msg)


def _normalize_citations(value: Any) -> list[dict[str, Any]]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [dict(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        parsed = json.loads(stripped)
        return [dict(item) for item in parsed]
    msg = f"unsupported citations value: {value!r}"
    raise ValueError(msg)


def _citation_id(seed: CitationSeed, metadata: CitationMetadata) -> str:
    if seed.pmid or metadata.pmid:
        return f"pmid:{seed.pmid or metadata.pmid}"
    if seed.doi or metadata.doi:
        return f"doi:{seed.doi or metadata.doi}"
    slug = "-".join((seed.title or metadata.title).lower().split())
    return f"manual:{slug}:{seed.year or metadata.year}"
