from __future__ import annotations

import json
import sys
from pathlib import Path

from autolab.core.enums import ArtifactType, FailureClass, SimulatorKind
from autolab.core.models import (
    Candidate,
    ExperimentSpec,
    GeometrySpec,
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


class MeepSimulator(WorkflowBackedSimulator):
    simulator_name = "meep"
    simulator_kind = SimulatorKind.MEEP

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._template_path = (
            Path(__file__).resolve().parent / "templates" / "meep" / "run_meep.py.j2"
        )

    @property
    def binary_name(self) -> str:
        configured = self._settings.simulators.meep_bin
        return sys.executable if configured == "python" else configured

    @property
    def enabled(self) -> bool:
        return self._settings.simulators.enable_meep

    @property
    def timeout_seconds(self) -> int:
        return self._settings.simulators.meep_timeout_seconds

    @property
    def command_wrapper(self) -> str | None:
        return self._settings.simulators.meep_wrapper

    @property
    def environment_overrides(self) -> dict[str, str]:
        return self._settings.simulators.meep_environment

    def build_task(self, candidate: Candidate) -> SimulationTask:
        geometry = GeometrySpec(
            kind="waveguide_block",
            parameters={
                "sx": float(candidate.values.get("sx", 16.0)),
                "sy": float(candidate.values.get("sy", 8.0)),
                "block_x": float(candidate.values.get("block_x", 1.0)),
                "block_y": float(candidate.values.get("block_y", 4.0)),
                "refractive_index": float(candidate.values.get("refractive_index", 3.4)),
            },
            units={"sx": "um", "sy": "um", "block_x": "um", "block_y": "um"},
        )
        return SimulationTask(
            name="meep_flux_scan",
            simulator=self.simulator_kind,
            parameters={
                **geometry.parameters,
                "resolution": int(candidate.values.get("resolution", 20)),
                "dpml": float(candidate.values.get("dpml", 1.0)),
                "fcen": float(candidate.values.get("fcen", 0.15)),
                "df": float(candidate.values.get("df", 0.1)),
                "nfreq": int(candidate.values.get("nfreq", 25)),
                "until": int(candidate.values.get("until", 50)),
            },
            geometry=geometry,
            expected_outputs=["meep_results.json", "stdout.log", "stderr.log"],
        )

    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]:
        template = Template(self._template_path.read_text(encoding="utf-8"))
        driver = template.render(**spec.parameters)
        driver_artifact = write_text_artifact(
            path=workdir / "run_meep.py",
            content=driver,
            artifact_type=ArtifactType.SCRIPT,
            artifact_role="python_driver",
            stage_name=spec.stage_name,
        )
        launch_script = write_text_artifact(
            path=workdir / "launch.sh",
            content=f"#!/usr/bin/env bash\nset -euo pipefail\n{self.binary_name} run_meep.py\n",
            artifact_type=ArtifactType.SCRIPT,
            artifact_role="launch_script",
            stage_name=spec.stage_name,
        )
        return [driver_artifact, launch_script]

    def build_command(self, spec: ExperimentSpec, workdir: Path) -> list[str]:
        return [self.binary_name, "run_meep.py"]

    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult:
        results_path = Path(execution.workdir_path) / "meep_results.json"
        metrics: dict[str, float] = {}
        timeseries: dict[str, list[float]] = {}
        errors: list[str] = []
        if results_path.exists():
            payload = json.loads(results_path.read_text(encoding="utf-8"))
            transmission = [float(value) for value in payload.get("transmission", [])]
            reflection = [float(value) for value in payload.get("reflection", [])]
            frequencies = [float(value) for value in payload.get("frequencies", [])]
            timeseries = {
                "transmission": transmission,
                "reflection": reflection,
                "frequencies": frequencies,
            }
            metrics = {
                "transmission_peak": max(transmission) if transmission else 0.0,
                "reflection_peak": max(reflection) if reflection else 0.0,
                "transmission_mean": sum(transmission) / len(transmission) if transmission else 0.0,
            }
        else:
            errors.append("missing meep_results.json")
        return SimulationParseResult(
            experiment_id=execution.experiment_id,
            campaign_id=execution.campaign_id,
            candidate_id=execution.candidate_id,
            simulator=self.simulator_kind,
            stage_name=execution.stage_name,
            status=execution.status,
            scalar_metrics=metrics,
            timeseries=timeseries,
            convergence=execution.status.value == "succeeded",
            warnings=[],
            parse_errors=errors,
            raw_output_references=[str(results_path)],
        )

    def validate_parsed(self, parsed: SimulationParseResult) -> SimulationValidationResult:
        reasons: list[str] = []
        status = "valid"
        failure_class = FailureClass.NONE
        if parsed.status.value != "succeeded":
            status = "invalid"
            failure_class = FailureClass.ENGINE
            reasons.append(f"stage status is {parsed.status.value}")
        if parsed.parse_errors:
            status = "invalid"
            failure_class = FailureClass.PARSE
            reasons.extend(parsed.parse_errors)
        if not parsed.timeseries.get("transmission"):
            status = "partial" if status == "valid" else status
            reasons.append("missing transmission spectrum")
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
