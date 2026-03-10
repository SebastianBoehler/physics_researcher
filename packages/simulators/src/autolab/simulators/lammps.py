from __future__ import annotations

from pathlib import Path

from autolab.core.enums import FailureClass, RunStatus, SimulatorKind
from autolab.core.models import Candidate, SimulationInput, SimulationResult, ValidationReport
from autolab.core.settings import Settings
from autolab.simulators.types import JobHandle, PreparedRun, SimulationStatus, ValidationOutcome


class LammpsSimulator:
    simulator_name = "lammps"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def prepare_input(self, candidate: Candidate) -> PreparedRun:
        template_path = Path("integrations/lammps/templates/in.lammps")
        payload = {"candidate_values": candidate.values, "template_path": str(template_path)}
        simulation_input = SimulationInput(
            campaign_id=candidate.campaign_id,
            candidate_id=candidate.id,
            simulator=SimulatorKind.LAMMPS,
            payload=payload,
            seed=int(candidate.metadata.get("seed", 42)),
            working_directory=str(self._settings.app.artifact_root / str(candidate.id) / "lammps"),
        )
        return PreparedRun(
            campaign_id=candidate.campaign_id,
            candidate_id=candidate.id,
            simulator=SimulatorKind.LAMMPS,
            simulation_input=simulation_input,
            command=["lmp", "-in", str(template_path)],
            metadata={"enabled": self._settings.simulators.enable_lammps},
        )

    def run(self, prepared_run: PreparedRun) -> JobHandle:
        return JobHandle(
            id=f"lammps-{prepared_run.id}",
            prepared_run_id=prepared_run.id,
            simulator=SimulatorKind.LAMMPS,
            status=RunStatus.QUEUED,
            metadata={"enabled": self._settings.simulators.enable_lammps},
        )

    def poll(self, job_handle: JobHandle) -> SimulationStatus:
        return SimulationStatus(
            job_id=job_handle.id,
            status=RunStatus.FAILED,
            terminal=True,
            message="LAMMPS adapter scaffold only; backend not enabled by default.",
        )

    def parse(self, job_handle: JobHandle) -> SimulationResult:
        return SimulationResult(
            run_id=job_handle.prepared_run_id,
            candidate_id=job_handle.prepared_run_id,
            simulator=SimulatorKind.LAMMPS,
            status=RunStatus.FAILED,
            metrics={},
            raw_outputs={"job_id": job_handle.id},
            summary="LAMMPS adapter scaffold only.",
            artifact_paths=[],
            failure_class=FailureClass.ENGINE,
        )

    def validate(self, result: SimulationResult) -> ValidationOutcome:
        return ValidationOutcome(
            report=ValidationReport(
                run_id=result.run_id,
                valid=False,
                issues=[],
                derived_metrics=result.metrics,
            ),
            metadata={"reason": "scaffold"},
        )
