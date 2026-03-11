from __future__ import annotations

import json
from pathlib import Path

from autolab.core.enums import RunStatus, SimulatorKind
from autolab.core.models import (
    Candidate,
    SimulationExecutionRecord,
    SimulationStage,
    SimulationTask,
    SimulationWorkflow,
)
from autolab.core.settings import get_settings
from autolab.simulators.meep import MeepSimulator


def test_meep_splitter_task_includes_device_parameters() -> None:
    candidate = Candidate(
        campaign_id="00000000-0000-0000-0000-000000000501",
        values={
            "device_kind": "splitter",
            "block_x": 3.2,
            "block_y": 4.5,
            "arm_separation": 2.8,
            "output_width": 0.9,
        },
    )

    task = MeepSimulator(get_settings()).build_task(candidate)

    assert task.parameters["device_kind"] == "splitter"
    assert task.parameters["arm_separation"] == 2.8
    assert task.parameters["output_width"] == 0.9
    assert task.geometry is not None
    assert task.geometry.kind == "splitter"


def test_meep_task_includes_optional_second_block_parameters() -> None:
    candidate = Candidate(
        campaign_id="00000000-0000-0000-0000-000000000502",
        values={
            "device_kind": "demux",
            "block2_x": 1.3,
            "block2_y": 0.8,
            "block2_center_x": 0.4,
            "block2_center_y": -0.6,
        },
    )

    task = MeepSimulator(get_settings()).build_task(candidate)

    assert task.parameters["block2_x"] == 1.3
    assert task.parameters["block2_y"] == 0.8
    assert task.parameters["block2_center_x"] == 0.4
    assert task.parameters["block2_center_y"] == -0.6
    assert task.geometry is not None
    assert task.geometry.parameters["block2_x"] == 1.3


def test_meep_demux_parser_extracts_routing_metrics(tmp_path: Path) -> None:
    payload = {
        "device_kind": "demux",
        "frequencies": [0.12, 0.14, 0.16, 0.18],
        "route_targets": {"low": "upper", "high": "lower"},
        "monitors": {
            "reflection": [0.12, 0.08, 0.06, 0.05],
            "upper": [0.92, 0.88, 0.20, 0.12],
            "lower": [0.09, 0.11, 0.81, 0.84],
        },
    }
    (tmp_path / "meep_results.json").write_text(json.dumps(payload), encoding="utf-8")

    execution = SimulationExecutionRecord(
        experiment_id="00000000-0000-0000-0000-000000000510",
        campaign_id="00000000-0000-0000-0000-000000000511",
        candidate_id="00000000-0000-0000-0000-000000000512",
        simulator=SimulatorKind.MEEP,
        stage_name="primary",
        workdir_path=str(tmp_path),
        status=RunStatus.SUCCEEDED,
    )

    parsed = MeepSimulator(get_settings()).parse_outputs(execution)

    assert parsed.scalar_metrics["upper_low_mean"] > 0.8
    assert parsed.scalar_metrics["lower_high_mean"] > 0.8
    assert parsed.scalar_metrics["demux_score"] > 1.4
    assert parsed.scalar_metrics["demux_target_mean"] > parsed.scalar_metrics["demux_leakage_mean"]
    assert parsed.scalar_metrics["device_score"] > 100.0


def test_meep_workflow_spec_merges_candidate_values_over_stage_defaults() -> None:
    candidate = Candidate(
        campaign_id="00000000-0000-0000-0000-000000000520",
        values={"block_x": 4.2, "block_y": 5.1},
    )
    workflow = SimulationWorkflow(
        name="meep-override-check",
        stages=[
            SimulationStage(
                name="meep",
                simulator=SimulatorKind.MEEP,
                task=SimulationTask(
                    name="meep_flux_scan",
                    simulator=SimulatorKind.MEEP,
                    parameters={"device_kind": "waveguide_block", "block_x": 1.0, "block_y": 2.0},
                ),
            )
        ],
    )

    spec = MeepSimulator(get_settings()).create_experiment_spec(
        candidate,
        workflow=workflow,
        stage_name="meep",
    )

    assert spec.parameters["block_x"] == 4.2
    assert spec.parameters["block_y"] == 5.1
    assert spec.parameters["device_kind"] == "waveguide_block"
