from __future__ import annotations

import json
from pathlib import Path

from autolab.campaigns import CampaignService
from autolab.core.models import Campaign
from autolab.core.settings import Settings
from autolab.simulators.registry import build_default_registry
from autolab.storage.db import init_db


def test_campaign_step_executes_batch_in_parallel_when_enabled(tmp_path: Path) -> None:
    settings = Settings()
    settings.database.url = f"sqlite+pysqlite:///{tmp_path / 'parallel.db'}"
    settings.app.artifact_root = tmp_path / "artifacts"
    settings.app.max_parallel_runs = 2
    settings.simulators.working_directory_root = tmp_path / "artifacts" / "runs"
    settings.simulators.enable_openmm = True
    settings.ensure_directories()
    init_db(settings)

    payload = json.loads(
        Path("examples/campaigns/openmm_lj_pair_equilibrium.json").read_text(encoding="utf-8")
    )
    payload["budget"]["max_runs"] = 2
    payload["budget"]["batch_size"] = 2
    campaign = Campaign.model_validate(payload)

    service = CampaignService(settings, build_default_registry(settings))
    created = service.create_campaign(campaign)
    service.start_campaign(created.id)

    outcome = service.step_campaign(created.id)
    runs = service.list_runs(created.id)

    assert outcome["status"] == "completed"
    assert len(outcome["run_ids"]) == 2
    assert len(runs) == 2
    assert all(run.status.value == "succeeded" for run in runs)
