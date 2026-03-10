from __future__ import annotations

import json
from pathlib import Path

import pytest
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


def test_step_records_workflow_stage_metadata() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}
    payload = json.loads(
        Path("examples/campaigns/cross_simulator_transfer_verification.json").read_text(
            encoding="utf-8"
        )
    )

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
    assert all("workflow_name" in run["metadata"] for run in runs)
    assert all("workflow_stage_order" in run["metadata"] for run in runs)
    assert all("stage_results" in run["metadata"] for run in runs)
    assert all("validation" in run["metadata"] for run in runs)


@pytest.mark.parametrize(
    ("example_dir", "example_name"),
    [
        ("examples/campaigns", "openmm_protein_relaxation.json"),
        ("examples/campaigns", "openmm_lj_pair_equilibrium.json"),
        ("examples/campaigns", "meep_waveguide_inverse_screen.json"),
        ("examples/campaigns", "qe_to_lammps_forcefield_bootstrap.json"),
        ("benchmarks/meep_inverse_design/campaigns", "waveguide_lowres_screen.json"),
        ("benchmarks/meep_inverse_design/campaigns", "qe_to_meep_transfer_screen.json"),
    ],
)
def test_additional_example_campaigns_execute_inline(example_dir: str, example_name: str) -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}
    payload = json.loads(Path(example_dir, example_name).read_text(encoding="utf-8"))

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
    assert runs_response.json()["runs"]
