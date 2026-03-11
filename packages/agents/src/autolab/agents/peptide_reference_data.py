from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from autolab.agents.peptide_models import (
    PeptideReferenceDataset,
    PeptideReferenceDatasetManifest,
)

_MANIFEST_FILENAME = "peptide_references.manifest.json"


@lru_cache(maxsize=1)
def load_reference_manifest() -> PeptideReferenceDatasetManifest:
    manifest_path = files("autolab.agents.data").joinpath(_MANIFEST_FILENAME)
    with manifest_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return PeptideReferenceDatasetManifest.model_validate(payload)


@lru_cache(maxsize=4)
def load_reference_dataset(version: str | None = None) -> PeptideReferenceDataset:
    manifest = load_reference_manifest()
    selected_version = version or manifest.default_version
    dataset_file = next(
        (
            dataset.filename
            for dataset in manifest.datasets
            if dataset.version == selected_version
        ),
        None,
    )
    if dataset_file is None:
        msg = f"unknown peptide reference dataset version: {selected_version}"
        raise ValueError(msg)
    dataset_path = files("autolab.agents.data").joinpath(dataset_file)
    with dataset_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return PeptideReferenceDataset.model_validate(payload)
