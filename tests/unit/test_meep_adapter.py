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


def test_meep_adjoint_task_uses_separate_task_family() -> None:
    candidate = Candidate(
        campaign_id="00000000-0000-0000-0000-000000000503",
        values={
            "optimization_mode": "adjoint",
            "device_kind": "adjoint_splitter",
            "design_region_x": 3.1,
            "design_region_y": 2.2,
            "adjoint_iterations": 5,
        },
    )

    task = MeepSimulator(get_settings()).build_task(candidate)

    assert task.name == "meep_adjoint_device"
    assert task.parameters["design_region_x"] == 3.1
    assert task.parameters["adjoint_iterations"] == 5
    assert "adjoint_results.json" in task.expected_outputs


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
    assert parsed.scalar_metrics["device_score"] > 10.0


def test_meep_adjoint_parser_extracts_optimization_metrics(tmp_path: Path) -> None:
    payload = {
        "device_kind": "splitter",
        "frequencies": [0.145, 0.15, 0.155],
        "objective_history": [0.18, 0.31, 0.42],
        "beta_history": [2.0, 2.8, 3.92],
        "gradient_norm_history": [0.9, 0.5, 0.2],
        "final_design_weights": [0.02, 0.98, 0.87, 0.12],
        "monitors": {
            "upper": [0.42, 0.46, 0.43],
            "lower": [0.41, 0.45, 0.42],
            "transmission": [0.83, 0.91, 0.85],
        },
    }
    (tmp_path / "adjoint_results.json").write_text(json.dumps(payload), encoding="utf-8")

    execution = SimulationExecutionRecord(
        experiment_id="00000000-0000-0000-0000-000000000513",
        campaign_id="00000000-0000-0000-0000-000000000514",
        candidate_id="00000000-0000-0000-0000-000000000515",
        simulator=SimulatorKind.MEEP,
        stage_name="meep",
        workdir_path=str(tmp_path),
        status=RunStatus.SUCCEEDED,
    )

    parsed = MeepSimulator(get_settings()).parse_outputs(execution)

    assert parsed.metadata["task_name"] == "meep_adjoint_device"
    assert parsed.scalar_metrics["adjoint_iteration_count"] == 3.0
    assert parsed.scalar_metrics["adjoint_best_objective"] == 0.42
    assert parsed.scalar_metrics["splitter_excess_loss_db"] < 1.0
    assert parsed.scalar_metrics["split_imbalance_db"] < 0.2
    assert parsed.scalar_metrics["design_binary_fraction"] == 0.5
    assert parsed.timeseries["objective_history"] == [0.18, 0.31, 0.42]


def test_meep_adjoint_parser_surfaces_runtime_blocker(tmp_path: Path) -> None:
    payload = {
        "status": "failed",
        "driver": "run_meep_adjoint.py",
        "exit_code": 134,
        "message": "Adjoint MEEP driver exited before producing adjoint_results.json. Inspect stderr.log for the native failure.",
    }
    (tmp_path / "adjoint_error.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "stderr.log").write_text(
        "Assertion failed: (changed_materials), function step_db, file step_db.cpp, line 40.\n",
        encoding="utf-8",
    )

    execution = SimulationExecutionRecord(
        experiment_id="00000000-0000-0000-0000-000000000516",
        campaign_id="00000000-0000-0000-0000-000000000517",
        candidate_id="00000000-0000-0000-0000-000000000518",
        simulator=SimulatorKind.MEEP,
        stage_name="meep",
        workdir_path=str(tmp_path),
        status=RunStatus.FAILED,
    )

    simulator = MeepSimulator(get_settings())
    parsed = simulator.parse_outputs(execution)
    validation = simulator.validate_parsed(parsed)

    assert parsed.metadata["task_name"] == "meep_adjoint_device"
    assert parsed.metadata["adjoint_exit_code"] == 134
    assert "changed_materials" in parsed.metadata["adjoint_runtime_blocker"]
    assert validation.failure_class.value == "engine"
    assert any("changed_materials" in reason for reason in validation.reasons)


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


def test_meep_adjoint_workflow_uses_adjoint_driver_filename(tmp_path: Path) -> None:
    candidate = Candidate(
        campaign_id="00000000-0000-0000-0000-000000000521",
        values={},
    )
    workflow = SimulationWorkflow(
        name="meep-adjoint-check",
        stages=[
            SimulationStage(
                name="meep",
                simulator=SimulatorKind.MEEP,
                task=SimulationTask(
                    name="meep_adjoint_device",
                    simulator=SimulatorKind.MEEP,
                    parameters={"device_kind": "adjoint_splitter"},
                ),
            )
        ],
    )

    spec = MeepSimulator(get_settings()).create_experiment_spec(
        candidate,
        workflow=workflow,
        stage_name="meep",
    )

    simulator = MeepSimulator(get_settings())
    generated = simulator.generate_inputs(spec, tmp_path)

    assert simulator.build_command(spec, tmp_path) == ["bash", "launch.sh"]
    assert any(str(artifact.path).endswith("run_meep_adjoint.py") for artifact in generated)
    assert any(str(artifact.path).endswith("launch.sh") for artifact in generated)
