from __future__ import annotations

import json
from pathlib import Path

from autolab.api.main import app
from fastapi.testclient import TestClient


def test_campaign_lifecycle() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}
    payload = json.loads(Path("examples/campaigns/demo_campaign.json").read_text(encoding="utf-8"))

    create_response = client.post("/campaigns", json=payload, headers=headers)
    assert create_response.status_code == 201
    campaign = create_response.json()

    start_response = client.post(f"/campaigns/{campaign['id']}/start", headers=headers)
    assert start_response.status_code == 200

    step_response = client.post(
        f"/campaigns/{campaign['id']}/step",
        json={"execute_inline": True},
        headers=headers,
    )
    assert step_response.status_code == 200
    assert step_response.json()["run_ids"]

    runs_response = client.get(f"/campaigns/{campaign['id']}/runs", headers=headers)
    assert runs_response.status_code == 200
    assert len(runs_response.json()["runs"]) >= 1


def test_step_marks_constraint_violations_in_validation_metadata() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}
    payload = json.loads(
        Path("examples/campaigns/baseline_conductivity.json").read_text(encoding="utf-8")
    )
    payload["constraints"] = [
        {
            "name": "impossible_cost_limit",
            "metric_key": "cost",
            "operator": "lt",
            "threshold": 10.0,
        }
    ]

    campaign = client.post("/campaigns", json=payload, headers=headers).json()
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)
    step_response = client.post(
        f"/campaigns/{campaign['id']}/step",
        json={"execute_inline": True},
        headers=headers,
    )

    assert step_response.status_code == 200
    runs_response = client.get(f"/campaigns/{campaign['id']}/runs", headers=headers)
    runs = runs_response.json()["runs"]
    assert runs
    assert all(run["metadata"]["validation"]["valid"] is False for run in runs)
    assert all(run["failure_class"] == "validation" for run in runs)
    assert all(run["metadata"]["constraint_validation"]["valid"] is False for run in runs)
    assert all(
        run["metadata"]["simulator_validation"]["run_id"] == run["id"] for run in runs
    )
