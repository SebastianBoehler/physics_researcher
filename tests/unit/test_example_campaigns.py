from __future__ import annotations

import json
from pathlib import Path

from autolab.api.schemas import CreateCampaignRequest


def test_example_campaigns_validate_against_api_schema() -> None:
    example_paths = sorted(Path("examples/campaigns").glob("*.json"))
    assert example_paths

    for path in example_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        campaign = CreateCampaignRequest.model_validate(payload)
        assert campaign.name
        assert campaign.budget.max_runs >= 1
