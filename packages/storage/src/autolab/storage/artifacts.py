from __future__ import annotations

from pathlib import Path
from uuid import UUID

from autolab.core.enums import ArtifactType
from autolab.core.models import ArtifactRecord
from autolab.core.settings import Settings
from autolab.core.utils import sha256_digest


class ArtifactStore:
    def __init__(self, settings: Settings) -> None:
        self._root = settings.app.artifact_root
        self._root.mkdir(parents=True, exist_ok=True)

    def write_text(
        self,
        campaign_id: UUID,
        run_id: UUID | None,
        artifact_type: ArtifactType,
        relative_path: str,
        content: str,
        media_type: str = "application/json",
    ) -> ArtifactRecord:
        path = self._root / str(campaign_id) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        digest = sha256_digest(content.encode("utf-8"))
        return ArtifactRecord(
            campaign_id=campaign_id,
            run_id=run_id,
            artifact_type=artifact_type,
            path=str(path),
            media_type=media_type,
            sha256=digest,
        )

    def read_text(self, artifact: ArtifactRecord) -> str:
        return Path(artifact.path).read_text(encoding="utf-8")
