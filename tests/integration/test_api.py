from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from autolab.api.main import app
from autolab.core.settings import get_settings
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

    campaign_list_response = client.get("/campaigns", headers=headers)
    assert campaign_list_response.status_code == 200
    assert any(
        listed_campaign["id"] == campaign["id"]
        for listed_campaign in campaign_list_response.json()["campaigns"]
    )


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


def test_thermoelectric_measurement_workflow_records_measured_metrics() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}
    payload = json.loads(
        Path("examples/campaigns/thermoelectric_sim_to_measurement_loop.json").read_text(
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
    assert all(run["metrics"]["power_factor"] > 0 for run in runs)
    assert all(run["metrics"]["electrical_conductivity"] > 0 for run in runs)
    assert all("measurement" in run["metadata"]["stage_results"] for run in runs)


def test_skill_catalog_endpoint_returns_registry_metadata() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}

    response = client.get("/skills?domain=simulation", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["skills"]
    assert any(skill["name"] == "launch_simulation_stage" for skill in payload["skills"])
    assert all(skill["domain"] == "simulation" for skill in payload["skills"])


def test_run_artifact_listing_supports_stage_filter() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}
    payload = json.loads(
        Path("examples/campaigns/thermoelectric_sim_to_measurement_loop.json").read_text(
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
    run_id = step_response.json()["run_ids"][0]

    all_artifacts = client.get(f"/runs/{run_id}/artifacts", headers=headers)
    fabrication_artifacts = client.get(
        f"/runs/{run_id}/artifacts?stage_name=fabrication_protocol", headers=headers
    )
    measurement_artifacts = client.get(
        f"/runs/{run_id}/artifacts?stage_name=measurement", headers=headers
    )

    assert all_artifacts.status_code == 200
    assert fabrication_artifacts.status_code == 200
    assert measurement_artifacts.status_code == 200
    assert all_artifacts.json()["artifacts"]
    assert fabrication_artifacts.json()["artifacts"]
    assert measurement_artifacts.json()["artifacts"]
    assert all(
        artifact["metadata"].get("stage_name") == "fabrication_protocol"
        for artifact in fabrication_artifacts.json()["artifacts"]
    )
    assert all(
        artifact["metadata"].get("stage_name") == "measurement"
        for artifact in measurement_artifacts.json()["artifacts"]
    )


def test_benchmark_report_index_endpoint_lists_reports() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}
    benchmark_name = f"test-api-benchmark-{uuid4().hex[:8]}"
    report_dir = get_settings().app.artifact_root / "benchmarks" / benchmark_name
    report_path = report_dir / "report.json"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "benchmark_name": benchmark_name,
                "description": "Temporary benchmark for API coverage.",
                "paper_hypothesis": "Benchmark reports can be indexed.",
                "primary_metric": "score",
                "generated_at": "2026-03-11T12:00:00+00:00",
                "task_reports": [{"campaign_name": "demo"}],
                "summary": {"task_count": 1, "mean_best_metric": 1.0},
            }
        ),
        encoding="utf-8",
    )

    try:
        response = client.get("/benchmarks/reports", headers=headers)
        assert response.status_code == 200
        reports = response.json()["reports"]
        entry = next(report for report in reports if report["benchmark_name"] == benchmark_name)
        assert entry["report_path"].endswith(f"{benchmark_name}/report.json")
        assert entry["task_count"] == 1
        assert entry["summary"]["mean_best_metric"] == 1.0
    finally:
        shutil.rmtree(report_dir)


@pytest.mark.parametrize(
    ("example_dir", "example_name"),
    [
        ("examples/campaigns", "openmm_protein_relaxation.json"),
        ("examples/campaigns", "openmm_lj_pair_equilibrium.json"),
        ("examples/campaigns", "meep_waveguide_inverse_screen.json"),
        ("examples/campaigns", "qe_to_lammps_forcefield_bootstrap.json"),
        ("examples/campaigns", "thermoelectric_sim_to_measurement_loop.json"),
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
