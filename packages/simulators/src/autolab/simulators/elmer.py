from __future__ import annotations

import re
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


class ElmerSimulator(WorkflowBackedSimulator):
    simulator_name = "elmer"
    simulator_kind = SimulatorKind.ELMER

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._template_path = (
            Path(__file__).resolve().parent / "templates" / "elmer" / "case.sif.j2"
        )

    @property
    def binary_name(self) -> str:
        return self._settings.simulators.elmer_solver_bin

    @property
    def enabled(self) -> bool:
        return self._settings.simulators.enable_elmer

    @property
    def timeout_seconds(self) -> int:
        return self._settings.simulators.elmer_timeout_seconds

    @property
    def command_wrapper(self) -> str | None:
        return self._settings.simulators.elmer_wrapper

    @property
    def environment_overrides(self) -> dict[str, str]:
        return self._settings.simulators.elmer_environment

    def build_task(self, candidate: Candidate) -> SimulationTask:
        return SimulationTask(
            name="elmer_case",
            simulator=self.simulator_kind,
            parameters={
                "steady_state_max_iterations": int(
                    candidate.values.get("steady_state_max_iterations", 10)
                ),
                "heat_conductivity": float(candidate.values.get("heat_conductivity", 10.0)),
            },
            expected_outputs=["case.sif", "stdout.log", "stderr.log"],
        )

    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]:
        template = Template(self._template_path.read_text(encoding="utf-8"))
        case_text = template.render(**spec.parameters)
        case_artifact = write_text_artifact(
            path=workdir / "case.sif",
            content=case_text,
            artifact_type=ArtifactType.INPUT,
            artifact_role="input_deck",
            stage_name=spec.stage_name,
        )
        return [case_artifact]

    def build_command(self, spec: ExperimentSpec, workdir: Path) -> list[str]:
        return [self.binary_name, "case.sif"]

    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult:
        stdout_path = Path(execution.workdir_path) / "stdout.log"
        text = stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else ""
        match = re.search(r"NORM\s*=\s*(-?\d+\.\d+E[+-]\d+)", text)
        metrics = {"residual_norm": float(match.group(1))} if match else {}
        return SimulationParseResult(
            experiment_id=execution.experiment_id,
            campaign_id=execution.campaign_id,
            candidate_id=execution.candidate_id,
            simulator=self.simulator_kind,
            stage_name=execution.stage_name,
            status=execution.status,
            scalar_metrics=metrics,
            convergence="converged" in text.lower(),
            warnings=[],
            parse_errors=[],
            raw_output_references=[str(stdout_path)],
        )

    def validate_parsed(self, parsed: SimulationParseResult) -> SimulationValidationResult:
        reasons: list[str] = []
        failure_class = FailureClass.NONE
        status = "valid"
        if parsed.status.value != "succeeded":
            status = "invalid"
            reasons.append(f"stage status is {parsed.status.value}")
            failure_class = FailureClass.ENGINE
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
