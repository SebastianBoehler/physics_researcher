from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autolab.core.enums import FailureClass, RunStatus, SimulatorKind
from autolab.core.models import Candidate, SimulationInput, SimulationResult, ValidationReport
from autolab.core.settings import Settings
from autolab.core.utils import sha256_digest, stable_json_dumps, write_text
from autolab.evaluation.validators import validate_constraints
from autolab.simulators.types import JobHandle, PreparedRun, SimulationStatus, ValidationOutcome
from autolab.telemetry import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class _FakeJobRecord:
    prepared_run: PreparedRun
    status: RunStatus = RunStatus.QUEUED
    result_metrics: dict[str, float] = field(default_factory=dict)
    failure_class: FailureClass = FailureClass.NONE


class FakeSimulator:
    simulator_name = "fake"

    def __init__(self, settings: Settings, failure_policy: dict[str, str] | None = None) -> None:
        self._settings = settings
        self._failure_policy = failure_policy or {}
        self._jobs: dict[str, _FakeJobRecord] = {}

    def prepare_input(self, candidate: Candidate) -> PreparedRun:
        payload = {
            "candidate_values": candidate.values,
            "source": candidate.source,
            "failure_mode": candidate.metadata.get("failure_mode"),
        }
        simulation_input = SimulationInput(
            campaign_id=candidate.campaign_id,
            candidate_id=candidate.id,
            simulator=SimulatorKind.FAKE,
            payload=payload,
            seed=int(candidate.metadata.get("seed", 42)),
            working_directory=str(self._artifact_path(candidate.campaign_id, candidate.id)),
        )
        return PreparedRun(
            campaign_id=candidate.campaign_id,
            candidate_id=candidate.id,
            simulator=SimulatorKind.FAKE,
            simulation_input=simulation_input,
            command=["fake-simulator", "--run"],
            metadata={"prepared_sha256": sha256_digest(stable_json_dumps(payload).encode("utf-8"))},
        )

    def run(self, prepared_run: PreparedRun) -> JobHandle:
        metrics = self._evaluate_candidate(
            prepared_run.simulation_input.payload["candidate_values"]
        )
        failure_class = self._determine_failure(prepared_run)
        status = RunStatus.RUNNING if failure_class == FailureClass.TIMEOUT else RunStatus.SUCCEEDED
        if failure_class in {FailureClass.TRANSIENT, FailureClass.ENGINE, FailureClass.PARSE}:
            status = RunStatus.FAILED
        self._jobs[f"fake-{prepared_run.id}"] = _FakeJobRecord(
            prepared_run=prepared_run,
            status=status,
            result_metrics=metrics,
            failure_class=failure_class,
        )
        logger.info(
            "fake_simulator_job_created", job_id=f"fake-{prepared_run.id}", status=status.value
        )
        return JobHandle(
            id=f"fake-{prepared_run.id}",
            prepared_run_id=prepared_run.id,
            simulator=SimulatorKind.FAKE,
            status=status,
            metadata={"working_directory": prepared_run.simulation_input.working_directory},
        )

    def poll(self, job_handle: JobHandle) -> SimulationStatus:
        record = self._jobs[job_handle.id]
        if record.failure_class == FailureClass.TIMEOUT:
            record.status = RunStatus.TIMED_OUT
        return SimulationStatus(
            job_id=job_handle.id,
            status=record.status,
            terminal=record.status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.TIMED_OUT},
            message=record.failure_class.value,
        )

    def parse(self, job_handle: JobHandle) -> SimulationResult:
        record = self._jobs[job_handle.id]
        prepared_run = record.prepared_run
        artifact_dir = self._artifact_path(prepared_run.campaign_id, prepared_run.candidate_id)
        output_payload = {
            "job_id": job_handle.id,
            "metrics": record.result_metrics,
            "failure_class": record.failure_class.value,
        }
        output_sha = write_text(artifact_dir / "result.json", stable_json_dumps(output_payload))
        status = record.status
        if status == RunStatus.RUNNING:
            status = RunStatus.TIMED_OUT
        summary = (
            "Synthetic fake simulation completed."
            if status == RunStatus.SUCCEEDED
            else f"Fake simulation ended with {record.failure_class.value}."
        )
        return SimulationResult(
            run_id=prepared_run.id,
            candidate_id=prepared_run.candidate_id,
            simulator=SimulatorKind.FAKE,
            status=status,
            metrics=record.result_metrics,
            raw_outputs={"sha256": output_sha},
            summary=summary,
            artifact_paths=[str(artifact_dir / "result.json")],
            failure_class=record.failure_class,
        )

    def validate(self, result: SimulationResult) -> ValidationOutcome:
        report = ValidationReport(
            run_id=result.run_id,
            valid=result.status == RunStatus.SUCCEEDED
            and result.failure_class == FailureClass.NONE,
            issues=[],
            derived_metrics=result.metrics,
        )
        return ValidationOutcome(report=report, metadata={"simulator": self.simulator_name})

    def constraint_validation(
        self, metrics: dict[str, float], constraints: list[Any], run_id: str | None = None
    ) -> ValidationReport:
        return validate_constraints(constraints, metrics, run_id=run_id)

    def _artifact_path(self, campaign_id: Any, candidate_id: Any) -> Path:
        return self._settings.app.artifact_root / str(campaign_id) / str(candidate_id)

    def _determine_failure(self, prepared_run: PreparedRun) -> FailureClass:
        payload = prepared_run.simulation_input.payload
        explicit_mode = payload.get("failure_mode")
        if explicit_mode:
            return FailureClass(explicit_mode)
        conductivity = self._evaluate_candidate(payload["candidate_values"])["conductivity"]
        if conductivity < 1.0:
            return FailureClass.TRANSIENT
        return FailureClass.NONE

    def _evaluate_candidate(self, values: dict[str, float | int | str]) -> dict[str, float]:
        x = float(values.get("dopant_ratio", 0.2))
        y = float(values.get("anneal_temperature", 500.0))
        z = float(values.get("pressure", 1.0))
        additive = float(values.get("synthesis_time", 2.0))
        conductivity = (
            120.0 * math.exp(-((x - 0.34) ** 2) / 0.01) * math.exp(-((y - 640.0) ** 2) / 12000.0)
        )
        conductivity += 18.0 * math.cos(z * math.pi / 4.0) + additive * 4.0
        stability = 0.75 + 0.2 * math.exp(-((z - 2.2) ** 2) / 0.5) - abs(x - 0.3) * 0.4
        cost = 18.0 + x * 40.0 + z * 6.0 + additive * 1.3 + abs(y - 600.0) / 25.0
        return {
            "conductivity": round(conductivity, 4),
            "stability": round(stability, 4),
            "cost": round(cost, 4),
        }
