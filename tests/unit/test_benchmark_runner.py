from __future__ import annotations

import json
from pathlib import Path

import pytest

from autolab.api.schemas import CreateCampaignRequest
from autolab.cli.benchmarks import (
    build_summary,
    derive_step_budget,
    load_benchmark_manifest,
    summarize_campaign_runs,
)


def test_meep_benchmark_manifest_loads() -> None:
    manifest = load_benchmark_manifest(Path("benchmarks/meep_inverse_design/benchmark.json"))
    assert manifest.name == "meep-inverse-design-v1"
    assert len(manifest.campaigns) == 3
    assert manifest.primary_metric == "transmission_peak"


def test_openmm_benchmark_manifest_loads() -> None:
    manifest = load_benchmark_manifest(Path("benchmarks/openmm_lj_pair/benchmark.json"))
    assert manifest.name == "openmm-lj-pair-v1"
    assert manifest.primary_metric == "energy_gap_to_reference"
    assert manifest.evaluation["reference_best_metric"] == 0.0


def test_openmm_lj13_benchmark_manifest_loads() -> None:
    manifest = load_benchmark_manifest(Path("benchmarks/openmm_lj13_cluster/benchmark.json"))
    assert manifest.name == "openmm-lj13-cluster-v1"
    assert manifest.primary_metric == "energy_gap_to_reference"
    assert manifest.evaluation["reference_atom_count"] == 13


def test_openmm_lj13_refined_benchmark_manifest_loads() -> None:
    manifest = load_benchmark_manifest(
        Path("benchmarks/openmm_lj13_cluster_refined/benchmark.json")
    )
    assert manifest.name == "openmm-lj13-cluster-refined-v1"
    assert manifest.primary_metric == "energy_gap_to_reference"
    assert manifest.evaluation["reference_atom_count"] == 13


def test_openmm_lj13_baseline_benchmark_manifest_loads() -> None:
    manifest = load_benchmark_manifest(Path("benchmarks/openmm_lj13_baselines/benchmark.json"))
    assert manifest.name == "openmm-lj13-baselines-v1"
    assert manifest.primary_metric == "energy_gap_to_reference"
    assert len(manifest.campaigns) == 12
    assert manifest.evaluation["low_gap_thresholds"] == [1e-5, 1e-6]
    assert manifest.evaluation["top_k_sizes"] == [3]


def test_meep_photonic_baseline_benchmark_manifest_loads() -> None:
    manifest = load_benchmark_manifest(
        Path("benchmarks/meep_photonic_devices/baselines_benchmark.json")
    )
    assert manifest.name == "meep-photonic-devices-baselines-v1"
    assert manifest.primary_metric == "device_score"
    assert len(manifest.campaigns) == 6


def test_meep_photonic_advanced_benchmark_manifest_loads() -> None:
    manifest = load_benchmark_manifest(
        Path("benchmarks/meep_photonic_devices/advanced_benchmark.json")
    )
    assert manifest.name == "meep-photonic-devices-advanced-v1"
    assert manifest.primary_metric == "device_score"
    assert len(manifest.campaigns) == 3
    assert manifest.evaluation["top_k_sizes"] == [3]


def test_thermoelectric_benchmark_manifest_loads() -> None:
    manifest = load_benchmark_manifest(Path("benchmarks/thermoelectric_measurement/benchmark.json"))
    assert manifest.name == "thermoelectric-measurement-v1"
    assert manifest.primary_metric == "power_factor"
    assert len(manifest.campaigns) == 3


def test_benchmark_campaigns_validate_against_api_schema() -> None:
    for path in sorted(Path("benchmarks/meep_inverse_design/campaigns").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        campaign = CreateCampaignRequest.model_validate(payload)
        assert campaign.name
        assert campaign.workflow is not None
    for path in sorted(Path("benchmarks/meep_photonic_devices/campaigns").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        campaign = CreateCampaignRequest.model_validate(payload)
        assert campaign.name.startswith("benchmark-meep-")
        assert campaign.workflow is not None
        if "advanced" in campaign.name:
            assert "optimizer" in campaign.metadata
    lj_cluster_payload = json.loads(
        Path(
            "benchmarks/openmm_lj13_cluster/campaigns/openmm_lj13_cluster_seed_31.json"
        ).read_text(encoding="utf-8")
    )
    lj_cluster_campaign = CreateCampaignRequest.model_validate(lj_cluster_payload)
    assert lj_cluster_campaign.name == "openmm-lj13-cluster-seed-31"
    assert len(lj_cluster_campaign.search_space.dimensions) == 43
    lj_cluster_refined_payload = json.loads(
        Path(
            "benchmarks/openmm_lj13_cluster_refined/campaigns/openmm_lj13_cluster_seed_31.json"
        ).read_text(encoding="utf-8")
    )
    lj_cluster_refined_campaign = CreateCampaignRequest.model_validate(
        lj_cluster_refined_payload
    )
    assert lj_cluster_refined_campaign.name == "openmm-lj13-cluster-refined-seed-31"
    assert len(lj_cluster_refined_campaign.search_space.dimensions) == 46
    for path in sorted(Path("benchmarks/openmm_lj13_baselines/campaigns").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        campaign = CreateCampaignRequest.model_validate(payload)
        assert campaign.name.startswith("openmm-lj13-cluster-")
        assert campaign.metadata["optimizer"]["algorithm"] in {"bayesian_gp", "random_search"}
    for path in sorted(Path("benchmarks/thermoelectric_measurement/campaigns").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        campaign = CreateCampaignRequest.model_validate(payload)
        assert campaign.name.startswith("thermoelectric-")
        assert campaign.workflow is not None


def test_derive_step_budget_from_campaign_budget() -> None:
    payload = {"budget": {"max_runs": 5, "batch_size": 2}}
    assert derive_step_budget(payload, max_steps=None) == 4
    assert derive_step_budget(payload, max_steps=7) == 7


def test_summarize_campaign_runs_collects_metrics_and_coverage() -> None:
    summary = summarize_campaign_runs(
        campaign_name="benchmark-meep",
        campaign_payload={
            "objectives": [
                {
                    "metric_key": "transmission_peak",
                    "direction": "maximize",
                }
            ],
            "workflow": {
                "stages": [{"name": "meep"}],
            }
        },
        campaign_response={"id": "cid", "simulator": "meep", "status": "completed"},
        primary_metric="transmission_peak",
        step_history=[{"status": "running"}, {"status": "completed"}],
        runs=[
            {
                "status": "succeeded",
                "metrics": {"transmission_peak": 0.8},
                "metadata": {
                    "workflow_name": "wf",
                    "stage_results": {"meep": {"status": "succeeded"}},
                    "validation": {"valid": True},
                },
            },
            {
                "status": "failed",
                "metrics": {"transmission_peak": 0.2},
                "metadata": {
                    "workflow_name": "wf",
                    "stage_results": {"meep": {"status": "failed"}},
                    "validation": {"valid": False},
                },
            },
        ],
    )

    assert summary["best_metric"] == 0.8
    assert summary["mean_metric"] == 0.5
    assert summary["succeeded_runs"] == 1
    assert summary["failed_runs"] == 1
    assert summary["timed_out_runs"] == 0
    assert summary["status_counts"]["succeeded"] == 1
    assert summary["metric_direction"] == "maximize"
    assert summary["artifact_coverage"] == 1.0
    assert summary["workflow_stage_coverage"] == 1.0
    assert summary["metric_history"] == [0.8, 0.2]
    assert summary["best_so_far_history"] == [0.8, 0.8]
    assert summary["median_metric"] == 0.5
    assert summary["top_k_mean_by_size"]["top_3"] == 0.5


def test_summarize_campaign_runs_respects_minimize_direction() -> None:
    summary = summarize_campaign_runs(
        campaign_name="benchmark-openmm",
        campaign_payload={
            "objectives": [
                {
                    "metric_key": "energy_gap_to_reference",
                    "direction": "minimize",
                }
            ]
        },
        campaign_response={"id": "cid", "simulator": "openmm", "status": "completed"},
        primary_metric="energy_gap_to_reference",
        step_history=[],
        runs=[
            {"status": "succeeded", "metrics": {"energy_gap_to_reference": 0.9}, "metadata": {}},
            {"status": "succeeded", "metrics": {"energy_gap_to_reference": 0.04}, "metadata": {}},
        ],
    )
    assert summary["best_metric"] == 0.04
    assert summary["metric_direction"] == "minimize"
    assert summary["metric_history"] == [0.9, 0.04]
    assert summary["best_so_far_history"] == [0.9, 0.04]
    assert summary["median_metric"] == pytest.approx(0.47)
    assert summary["top_k_mean_by_size"]["top_3"] == pytest.approx(0.47)


def test_build_summary_tracks_gap_to_reference() -> None:
    summary = build_summary(
        [
            {"status": "completed", "failed_runs": 0, "best_metric": 0.05},
            {"status": "completed", "failed_runs": 0, "best_metric": 0.02},
        ],
        {
            "reference_best_metric": 0.0,
            "reference_direction": "minimize",
        },
    )
    assert summary["reference_best_metric"] == 0.0
    assert summary["reference_direction"] == "minimize"
    assert summary["best_observed_gap_to_reference"] == 0.02


def test_build_summary_groups_baselines() -> None:
    summary = build_summary(
        [
            {
                "status": "completed",
                "failed_runs": 0,
                "best_metric": 0.05,
                "median_metric": 0.08,
                "run_count": 2,
                "baseline_name": "bayesian_gp",
                "optimizer_algorithm": "bayesian_gp",
                "low_gap_hits_by_threshold": {"1e-05": 1, "1e-06": 0},
                "top_k_mean_by_size": {"top_3": 0.09},
            },
            {
                "status": "completed",
                "failed_runs": 0,
                "best_metric": 0.02,
                "median_metric": 0.03,
                "run_count": 2,
                "baseline_name": "random_search",
                "optimizer_algorithm": "random_search",
                "low_gap_hits_by_threshold": {"1e-05": 2, "1e-06": 1},
                "top_k_mean_by_size": {"top_3": 0.04},
            },
        ],
        {
            "reference_best_metric": 0.0,
            "reference_direction": "minimize",
            "low_gap_thresholds": [1e-5, 1e-6],
            "top_k_sizes": [3],
        },
    )
    assert summary["baseline_summaries"][0]["baseline_name"] == "bayesian_gp"
    assert summary["baseline_summaries"][1]["baseline_name"] == "random_search"
    assert summary["low_gap_hits_by_threshold"]["1e-05"] == 3
    assert summary["low_gap_rate_by_threshold"]["1e-06"] == 0.25
    assert summary["median_best_metric"] == 0.035
    assert summary["mean_median_metric"] == 0.055
    assert summary["top_k_mean_by_size"]["top_3"] == 0.065
