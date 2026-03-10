from __future__ import annotations

import json
from pathlib import Path

from autolab.api.main import app
from fastapi.testclient import TestClient


def test_demo_campaign_closed_loop() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}
    payload = json.loads(Path("examples/campaigns/demo_campaign.json").read_text(encoding="utf-8"))

    campaign = client.post("/campaigns", json=payload, headers=headers).json()
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)
    first_step = client.post(
        f"/campaigns/{campaign['id']}/step",
        json={"execute_inline": True},
        headers=headers,
    )
    second_step = client.post(
        f"/campaigns/{campaign['id']}/step",
        json={"execute_inline": True},
        headers=headers,
    )

    assert first_step.status_code == 200
    assert second_step.status_code == 200
    runs = client.get(f"/campaigns/{campaign['id']}/runs", headers=headers).json()["runs"]
    assert len(runs) == 4
    assert all(run["simulator"] == "lammps" for run in runs)
    assert all("workflow_stage_order" in run["metadata"] for run in runs)


def test_step_returns_updated_campaign_status_when_budget_is_exhausted() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}
    payload = json.loads(Path("examples/campaigns/demo_campaign.json").read_text(encoding="utf-8"))
    payload["budget"]["max_runs"] = 1
    payload["budget"]["batch_size"] = 1

    campaign = client.post("/campaigns", json=payload, headers=headers).json()
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)
    step_response = client.post(
        f"/campaigns/{campaign['id']}/step",
        json={"execute_inline": True},
        headers=headers,
    )

    assert step_response.status_code == 200
    assert step_response.json()["status"] == "completed"
    refreshed = client.get(f"/campaigns/{campaign['id']}", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "completed"
