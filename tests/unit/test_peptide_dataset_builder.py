from __future__ import annotations

import json
from pathlib import Path

from autolab.agents.citation_metadata import CitationMetadata
from autolab.agents.peptide_dataset_builder import (
    PeptideReferenceDatasetBuilder,
    update_dataset_manifest,
)
from autolab.agents.peptide_reference_data import (
    load_reference_dataset,
    load_reference_manifest,
)


class StubResolver:
    def resolve(self, *, doi: str | None = None, pmid: str | None = None) -> CitationMetadata:
        identifier = pmid or doi or "unknown"
        return CitationMetadata(
            title=f"Resolved {identifier}",
            year=2024,
            journal="Stub Journal",
            url=f"https://example.test/{identifier}",
            doi=doi,
            pmid=pmid,
        )


def test_reference_manifest_loads_default_dataset() -> None:
    manifest = load_reference_manifest()
    dataset = load_reference_dataset()

    assert manifest.default_version == "1.1.0"
    assert dataset.version == manifest.default_version
    assert dataset.entries


def test_builder_loads_jsonl_and_enriches_citations(tmp_path: Path) -> None:
    seed_path = tmp_path / "seeds.jsonl"
    seed_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "peptide_id": "pep-1",
                        "name": "Pep 1",
                        "sequence": "EEMQRR",
                        "family": "neuromodulatory_cosmetic_peptide",
                        "claim_clusters": ["fewer_wrinkles"],
                        "mechanisms": ["cosmetic_neuromodulation"],
                        "rationale": "Example entry.",
                        "citations": [
                            {
                                "pmid": "12345678",
                                "evidence_type": "review",
                                "supports": ["fewer_wrinkles"],
                            }
                        ],
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    builder = PeptideReferenceDatasetBuilder(resolver=StubResolver())
    dataset = builder.build_dataset(
        seeds=builder.load_seed_records([seed_path]),
        dataset_id="test-dataset",
        version="1.1.0",
        scope="test_scope",
        description="test dataset",
        generated_on="2026-03-11",
    )

    assert dataset.version == "1.1.0"
    assert dataset.entries[0].evidence.citations[0].citation_id == "pmid:12345678"
    assert dataset.entries[0].evidence.citations[0].title == "Resolved 12345678"


def test_builder_loads_csv_and_updates_manifest(tmp_path: Path) -> None:
    csv_path = tmp_path / "seeds.csv"
    csv_path.write_text(
        (
            "peptide_id,name,sequence,family,claim_clusters,mechanisms,rationale,citations\n"
            'pep-2,Pep 2,KTTKS,lipopeptide_signal,"[""fewer_wrinkles""]","[""collagen_signal""]",'
            'Example entry.,"[{""doi"":""10.1000/example"",""evidence_type"":""clinical"",'
            '""supports"":[""fewer_wrinkles""]}]"\n'
        ),
        encoding="utf-8",
    )

    builder = PeptideReferenceDatasetBuilder(resolver=StubResolver())
    dataset = builder.build_dataset(
        seeds=builder.load_seed_records([csv_path]),
        dataset_id="test-dataset",
        version="1.1.0",
        scope="test_scope",
        description="test dataset",
        generated_on="2026-03-11",
    )
    output_path = tmp_path / "peptide_references.v1.1.0.json"
    manifest_path = tmp_path / "manifest.json"
    builder.write_dataset(dataset, output_path)
    update_dataset_manifest(
        manifest_path=manifest_path,
        dataset=dataset,
        filename=output_path.name,
        set_default=True,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert output_path.exists()
    assert manifest["default_version"] == "1.1.0"
    assert manifest["datasets"][0]["filename"] == "peptide_references.v1.1.0.json"
