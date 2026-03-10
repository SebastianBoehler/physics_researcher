from __future__ import annotations

import json
import mimetypes
import shutil
from pathlib import Path
from typing import Any

from autolab.core.enums import ArtifactType
from autolab.core.models import SimulationArtifact
from autolab.core.utils import sha256_digest, stable_json_dumps


def file_sha256(path: Path) -> str:
    return sha256_digest(path.read_bytes())


def write_text_artifact(
    path: Path,
    content: str,
    artifact_type: ArtifactType,
    artifact_role: str,
    stage_name: str,
    media_type: str = "text/plain",
    metadata: dict[str, Any] | None = None,
) -> SimulationArtifact:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return SimulationArtifact(
        artifact_type=artifact_type,
        artifact_role=artifact_role,
        path=str(path),
        media_type=media_type,
        sha256=sha256_digest(content.encode("utf-8")),
        stage_name=stage_name,
        metadata=metadata or {},
    )


def write_json_artifact(
    path: Path,
    payload: dict[str, Any],
    artifact_type: ArtifactType,
    artifact_role: str,
    stage_name: str,
    metadata: dict[str, Any] | None = None,
) -> SimulationArtifact:
    return write_text_artifact(
        path=path,
        content=stable_json_dumps(payload),
        artifact_type=artifact_type,
        artifact_role=artifact_role,
        stage_name=stage_name,
        media_type="application/json",
        metadata=metadata,
    )


def copy_file_artifact(
    source: Path,
    destination: Path,
    artifact_type: ArtifactType,
    artifact_role: str,
    stage_name: str,
    metadata: dict[str, Any] | None = None,
) -> SimulationArtifact:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    media_type = mimetypes.guess_type(destination.name)[0] or "application/octet-stream"
    return SimulationArtifact(
        artifact_type=artifact_type,
        artifact_role=artifact_role,
        path=str(destination),
        media_type=media_type,
        sha256=file_sha256(destination),
        stage_name=stage_name,
        metadata=metadata or {"source_path": str(source)},
    )


def list_files(workdir: Path) -> list[str]:
    if not workdir.exists():
        return []
    return sorted(str(path) for path in workdir.rglob("*") if path.is_file())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
