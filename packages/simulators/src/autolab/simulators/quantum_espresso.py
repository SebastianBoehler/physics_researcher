from __future__ import annotations

import re
from pathlib import Path

from autolab.core.enums import ArtifactType, FailureClass, SimulatorKind
from autolab.core.models import (
    Candidate,
    ExperimentSpec,
    MaterialCandidate,
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


class QuantumEspressoSimulator(WorkflowBackedSimulator):
    simulator_name = "quantum_espresso"
    simulator_kind = SimulatorKind.QUANTUM_ESPRESSO

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._template_path = (
            Path(__file__).resolve().parent / "templates" / "quantum_espresso" / "pw.in.j2"
        )

    @property
    def binary_name(self) -> str:
        return self._settings.simulators.qe_pw_bin

    @property
    def enabled(self) -> bool:
        return self._settings.simulators.enable_quantum_espresso

    @property
    def timeout_seconds(self) -> int:
        return self._settings.simulators.quantum_espresso_timeout_seconds

    @property
    def command_wrapper(self) -> str | None:
        return self._settings.simulators.quantum_espresso_wrapper

    @property
    def environment_overrides(self) -> dict[str, str]:
        return self._settings.simulators.quantum_espresso_environment

    def build_task(self, candidate: Candidate) -> SimulationTask:
        material = MaterialCandidate(
            name=str(candidate.values.get("material_name", "silicon")),
            formula=str(candidate.values.get("formula", "Si")),
            composition={"Si": 1},
        )
        return SimulationTask(
            name="qe_scf",
            simulator=self.simulator_kind,
            parameters={
                "calculation": "scf",
                "prefix": str(candidate.values.get("prefix", "autolab_qe")),
                "pseudo_dir": str(candidate.values.get("pseudo_dir", "./pseudo")),
                "outdir": str(candidate.values.get("outdir", "./tmp")),
                "ecutwfc": float(candidate.values.get("ecutwfc", 30.0)),
                "conv_thr": float(candidate.values.get("conv_thr", 1.0e-6)),
                "lattice_parameter": float(candidate.values.get("lattice_parameter", 10.2)),
                "kpoints": str(candidate.values.get("kpoints", "4 4 4 0 0 0")),
            },
            units={"ecutwfc": "Ry", "lattice_parameter": "bohr"},
            material=material,
            expected_outputs=["qe.in", "stdout.log", "stderr.log"],
        )

    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]:
        template = Template(self._template_path.read_text(encoding="utf-8"))
        input_text = template.render(**spec.parameters)
        input_artifact = write_text_artifact(
            path=workdir / "qe.in",
            content=input_text,
            artifact_type=ArtifactType.INPUT,
            artifact_role="input_deck",
            stage_name=spec.stage_name,
        )
        launch_script = write_text_artifact(
            path=workdir / "launch.sh",
            content=f"#!/usr/bin/env bash\nset -euo pipefail\n{self.binary_name} -in qe.in\n",
            artifact_type=ArtifactType.SCRIPT,
            artifact_role="launch_script",
            stage_name=spec.stage_name,
        )
        return [input_artifact, launch_script]

    def build_command(self, spec: ExperimentSpec, workdir: Path) -> list[str]:
        return [self.binary_name, "-in", str(workdir / "qe.in")]

    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult:
        stdout_path = Path(execution.workdir_path) / "stdout.log"
        text = stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else ""
        match = re.search(r"!\s+total energy\s+=\s+(-?\d+\.\d+)", text)
        metrics = {"total_energy_ry": float(match.group(1))} if match else {}
        convergence = "convergence has been achieved" in text.lower()
        errors = [] if match else ["missing total energy line"]
        return SimulationParseResult(
            experiment_id=execution.experiment_id,
            campaign_id=execution.campaign_id,
            candidate_id=execution.candidate_id,
            simulator=self.simulator_kind,
            stage_name=execution.stage_name,
            status=execution.status,
            scalar_metrics=metrics,
            convergence=convergence,
            warnings=[],
            parse_errors=errors,
            raw_output_references=[str(stdout_path)],
        )

    def validate_parsed(self, parsed: SimulationParseResult) -> SimulationValidationResult:
        status = "valid"
        reasons: list[str] = []
        failure_class = FailureClass.NONE
        if parsed.status.value != "succeeded":
            status = "invalid"
            failure_class = FailureClass.ENGINE
            reasons.append(f"stage status is {parsed.status.value}")
        if parsed.parse_errors:
            status = "invalid"
            failure_class = FailureClass.PARSE
            reasons.extend(parsed.parse_errors)
        if parsed.convergence is False:
            status = "partial" if status == "valid" else status
            reasons.append("SCF convergence not confirmed")
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
