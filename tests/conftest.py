from __future__ import annotations

from pathlib import Path

import pytest
from autolab.api.dependencies import (
    get_campaign_service,
    get_literature_research_service,
    get_review_service,
)
from autolab.core.settings import get_settings


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "autolab-test.db"
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("AUTOLAB_DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("AUTOLAB_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("AUTOLAB_EXECUTION_MODE", "sync")
    get_settings.cache_clear()
    get_campaign_service.cache_clear()
    get_literature_research_service.cache_clear()
    get_review_service.cache_clear()
