from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from autolab.core.enums import ArtifactType, FailureClass, SimulatorKind
from autolab.core.models import (
    Candidate,
    ExperimentSpec,
    SimulationArtifact,
    SimulationExecutionRecord,
    SimulationParseResult,
    SimulationTask,
    SimulationValidationResult,
)
from autolab.core.settings import Settings
from autolab.simulators.core.adapter import WorkflowBackedSimulator
from autolab.simulators.core.artifacts import write_text_artifact
from jinja2 import Template


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _cluster_positions(values: dict[str, Any], atom_count: int) -> list[list[float]]:
    positions: list[list[float]] = [[0.0, 0.0, 0.0]]
    if atom_count >= 2:
        positions.append([float(values.get("atom_1_x", 1.1)), 0.0, 0.0])
    if atom_count >= 3:
        positions.append(
            [
                float(values.get("atom_2_x", 0.55)),
                float(values.get("atom_2_y", 0.95)),
                0.0,
            ]
        )
    for atom_index in range(3, atom_count):
        positions.append(
            [
                float(values.get(f"atom_{atom_index}_x", 0.0)),
                float(values.get(f"atom_{atom_index}_y", 0.0)),
                float(values.get(f"atom_{atom_index}_z", 0.0)),
            ]
        )
    return positions


class OpenMMSimulator(WorkflowBackedSimulator):
    simulator_name = "openmm"
    simulator_kind = SimulatorKind.OPENMM

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._template_path = (
            Path(__file__).resolve().parent / "templates" / "openmm" / "run_openmm.py.j2"
        )

    @property
    def binary_name(self) -> str:
        configured = self._settings.simulators.openmm_bin
        return sys.executable if configured == "python" else configured

    @property
    def enabled(self) -> bool:
        return self._settings.simulators.enable_openmm

    @property
    def timeout_seconds(self) -> int:
        return self._settings.simulators.openmm_timeout_seconds

    @property
    def command_wrapper(self) -> str | None:
        return self._settings.simulators.openmm_wrapper

    @property
    def environment_overrides(self) -> dict[str, str]:
        return self._settings.simulators.openmm_environment

    def build_task(self, candidate: Candidate) -> SimulationTask:
        system_kind = str(candidate.values.get("system_kind", "harmonic_bond"))
        atom_count = int(candidate.values.get("atom_count", 2))
        minimize_energy = _as_bool(
            candidate.values.get("minimize_energy"),
            default=system_kind == "lj_cluster",
        )
        return SimulationTask(
            name=f"openmm_{system_kind}",
            simulator=self.simulator_kind,
            parameters={
                "system_kind": system_kind,
                "atom_count": atom_count,
                "temperature": float(candidate.values.get("temperature", 300.0)),
                "steps": int(candidate.values.get("steps", 50)),
                "spring_constant": float(candidate.values.get("spring_constant", 25.0)),
                "equilibrium_distance": float(candidate.values.get("equilibrium_distance", 0.3)),
                "initial_distance": float(candidate.values.get("initial_distance", 0.32)),
                "sigma": float(candidate.values.get("sigma", 0.34)),
                "epsilon": float(candidate.values.get("epsilon", 0.997)),
                "friction": float(candidate.values.get("friction", 1.0)),
                "step_size_fs": float(candidate.values.get("step_size_fs", 2.0)),
                "platform_name": str(candidate.values.get("platform_name", "CPU")),
                "cluster_positions": _cluster_positions(candidate.values, atom_count),
                "reference_cluster_energy": float(
                    candidate.values.get("reference_cluster_energy", -44.3268014185)
                ),
                "minimize_energy": minimize_energy,
                "minimization_tolerance": float(
                    candidate.values.get("minimization_tolerance", 1e-6 if minimize_energy else 10.0)
                ),
                "minimization_max_iterations": int(
                    candidate.values.get(
                        "minimization_max_iterations",
                        10000 if minimize_energy else 0,
                    )
                ),
            },
            units={
                "temperature": "kelvin",
                "equilibrium_distance": "nanometer",
                "initial_distance": "nanometer",
                "sigma": "nanometer",
                "epsilon": "kilojoule_per_mole",
                "friction": "1/picosecond",
                "step_size_fs": "femtosecond",
                "reference_cluster_energy": "kilojoule_per_mole",
                "minimization_tolerance": "kilojoule_per_mole/nanometer",
            },
            expected_outputs=["openmm_results.json", "stdout.log", "stderr.log"],
        )

    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]:
        template = Template(self._template_path.read_text(encoding="utf-8"))
        driver = template.render(**spec.parameters)
        driver_artifact = write_text_artifact(
            path=workdir / "run_openmm.py",
            content=driver,
            artifact_type=ArtifactType.SCRIPT,
            artifact_role="python_driver",
            stage_name=spec.stage_name,
        )
        launch_script = write_text_artifact(
            path=workdir / "launch.sh",
            content=f"#!/usr/bin/env bash\nset -euo pipefail\n{self.binary_name} run_openmm.py\n",
            artifact_type=ArtifactType.SCRIPT,
            artifact_role="launch_script",
            stage_name=spec.stage_name,
        )
        return [driver_artifact, launch_script]

    def build_command(self, spec: ExperimentSpec, workdir: Path) -> list[str]:
        return [self.binary_name, "run_openmm.py"]

    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult:
        results_path = Path(execution.workdir_path) / "openmm_results.json"
        metrics: dict[str, float] = {}
        warnings: list[str] = []
        errors: list[str] = []
        if results_path.exists():
            payload = json.loads(results_path.read_text(encoding="utf-8"))
            metrics = {
                "potential_energy": float(payload.get("potential_energy", 0.0)),
                "kinetic_energy": float(payload.get("kinetic_energy", 0.0)),
                "temperature": float(payload.get("temperature", 0.0)),
            }
            optional_scalar_keys = (
                "final_distance_nm",
                "reference_distance_nm",
                "distance_gap_to_reference",
                "reference_energy",
                "energy_gap_to_reference",
                "atom_count",
                "cluster_radius_nm",
                "min_pair_distance_nm",
                "pre_minimization_energy",
            )
            for key in optional_scalar_keys:
                if key in payload:
                    metrics[key] = float(payload[key])
        else:
            errors.append("missing openmm_results.json")
        return SimulationParseResult(
            experiment_id=execution.experiment_id,
            campaign_id=execution.campaign_id,
            candidate_id=execution.candidate_id,
            simulator=self.simulator_kind,
            stage_name=execution.stage_name,
            status=execution.status,
            scalar_metrics=metrics,
            convergence=execution.status.value == "succeeded",
            warnings=warnings,
            parse_errors=errors,
            raw_output_references=[str(results_path)],
            metadata={
                "system_kind": (
                    payload.get("system_kind", "unknown") if results_path.exists() else "unknown"
                ),
                "platform_name": (
                    payload.get("platform_name", "unknown") if results_path.exists() else "unknown"
                ),
            },
        )

    def validate_parsed(self, parsed: SimulationParseResult) -> SimulationValidationResult:
        failure_class = FailureClass.NONE
        status = "valid"
        reasons: list[str] = []
        if parsed.status.value != "succeeded":
            status = "invalid"
            failure_class = FailureClass.ENGINE
            reasons.append(f"stage status is {parsed.status.value}")
        if parsed.parse_errors:
            status = "invalid"
            failure_class = FailureClass.PARSE
            reasons.extend(parsed.parse_errors)
        return SimulationValidationResult(
            experiment_id=parsed.experiment_id,
            campaign_id=parsed.campaign_id,
            candidate_id=parsed.candidate_id,
            simulator=self.simulator_kind,
            stage_name=parsed.stage_name,
            status=status,
            reasons=reasons,
            failure_class=failure_class,
            derived_metrics=parsed.scalar_metrics,
        )
