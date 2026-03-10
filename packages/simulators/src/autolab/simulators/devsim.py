from __future__ import annotations

import json
import sys
from pathlib import Path

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


class DevsimSimulator(WorkflowBackedSimulator):
    simulator_name = "devsim"
    simulator_kind = SimulatorKind.DEVSIM

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._template_path = (
            Path(__file__).resolve().parent / "templates" / "devsim" / "run_devsim.py.j2"
        )

    @property
    def binary_name(self) -> str:
        configured = self._settings.simulators.devsim_bin
        return sys.executable if configured == "python" else configured

    @property
    def enabled(self) -> bool:
        return self._settings.simulators.enable_devsim

    @property
    def timeout_seconds(self) -> int:
        return self._settings.simulators.devsim_timeout_seconds

    @property
    def command_wrapper(self) -> str | None:
        return self._settings.simulators.devsim_wrapper

    @property
    def environment_overrides(self) -> dict[str, str]:
        return self._settings.simulators.devsim_environment

    def build_task(self, candidate: Candidate) -> SimulationTask:
        return SimulationTask(
            name="devsim_dc",
            simulator=self.simulator_kind,
            parameters={
                "device_name": str(candidate.values.get("device_name", "pn_diode")),
                "bias": float(candidate.values.get("bias", 0.2)),
            },
            expected_outputs=["devsim_results.json", "stdout.log", "stderr.log"],
        )

    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]:
        template = Template(self._template_path.read_text(encoding="utf-8"))
        driver = template.render(**spec.parameters)
        return [
            write_text_artifact(
                path=workdir / "run_devsim.py",
                content=driver,
                artifact_type=ArtifactType.SCRIPT,
                artifact_role="python_driver",
                stage_name=spec.stage_name,
            )
        ]

    def build_command(self, spec: ExperimentSpec, workdir: Path) -> list[str]:
        return [self.binary_name, "run_devsim.py"]

    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult:
        result_path = Path(execution.workdir_path) / "devsim_results.json"
        metrics: dict[str, float] = {}
        errors: list[str] = []
        if result_path.exists():
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            metrics = {"drain_current": float(payload.get("drain_current", 0.0))}
        else:
            errors.append("missing devsim_results.json")
        return SimulationParseResult(
            experiment_id=execution.experiment_id,
            campaign_id=execution.campaign_id,
            candidate_id=execution.candidate_id,
            simulator=self.simulator_kind,
            stage_name=execution.stage_name,
            status=execution.status,
            scalar_metrics=metrics,
            convergence=execution.status.value == "succeeded",
            warnings=[],
            parse_errors=errors,
            raw_output_references=[str(result_path)],
        )

    def validate_parsed(self, parsed: SimulationParseResult) -> SimulationValidationResult:
        status = (
            "valid" if parsed.status.value == "succeeded" and not parsed.parse_errors else "invalid"
        )
        return SimulationValidationResult(
            experiment_id=parsed.experiment_id,
            campaign_id=parsed.campaign_id,
            candidate_id=parsed.candidate_id,
            simulator=self.simulator_kind,
            stage_name=parsed.stage_name,
            status=status,
            reasons=parsed.parse_errors,
            failure_class=FailureClass.NONE if status == "valid" else FailureClass.PARSE,
            derived_metrics=parsed.scalar_metrics,
        )
