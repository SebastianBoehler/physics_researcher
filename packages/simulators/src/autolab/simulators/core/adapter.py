from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

from autolab.core.enums import ArtifactType, FailureClass, RunStatus, SimulatorKind
from autolab.core.models import (
    Candidate,
    ExperimentSpec,
    SimulationArtifact,
    SimulationExecutionRecord,
    SimulationInput,
    SimulationParseResult,
    SimulationResult,
    SimulationTask,
    SimulationValidationResult,
    SimulationWorkflow,
    ValidationIssue,
    ValidationReport,
)
from autolab.core.settings import Settings
from autolab.core.utils import sha256_digest, stable_json_dumps
from autolab.simulators.base import SimulatorBackend
from autolab.simulators.core.artifacts import list_files, write_json_artifact
from autolab.simulators.core.manifests import write_manifest
from autolab.simulators.core.runner import BinaryNotAvailableError, ProcessRunner
from autolab.simulators.core.workflows import build_single_stage_workflow, stage_workdir
from autolab.simulators.types import JobHandle, PreparedRun, SimulationStatus, ValidationOutcome


class SimulatorAdapter(Protocol):
    name: str

    def supports(self, task: SimulationTask) -> bool: ...
    def build_workdir(self, spec: ExperimentSpec) -> Path: ...
    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]: ...
    def launch(self, spec: ExperimentSpec, workdir: Path) -> SimulationExecutionRecord: ...
    def poll(self, execution: SimulationExecutionRecord) -> SimulationExecutionRecord: ...
    def collect_outputs(self, execution: SimulationExecutionRecord) -> list[SimulationArtifact]: ...
    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult: ...
    def validate(self, parsed: SimulationParseResult) -> SimulationValidationResult: ...


class WorkflowBackedSimulator(SimulatorBackend, ABC):
    simulator_name: str
    simulator_kind: SimulatorKind
    adapter_version = "0.1.0"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._runner = ProcessRunner()
        self._executions: dict[str, SimulationExecutionRecord] = {}
        self._parse_results: dict[str, SimulationParseResult] = {}
        self._validation_results: dict[str, SimulationValidationResult] = {}

    @property
    @abstractmethod
    def binary_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def enabled(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def timeout_seconds(self) -> int:
        raise NotImplementedError

    @property
    def command_wrapper(self) -> str | None:
        return None

    @property
    def environment_overrides(self) -> dict[str, str]:
        return {}

    def supports(self, task: SimulationTask) -> bool:
        return task.simulator == self.simulator_kind

    @abstractmethod
    def build_task(self, candidate: Candidate) -> SimulationTask:
        raise NotImplementedError

    @abstractmethod
    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]:
        raise NotImplementedError

    @abstractmethod
    def build_command(self, spec: ExperimentSpec, workdir: Path) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult:
        raise NotImplementedError

    @abstractmethod
    def validate_parsed(self, parsed: SimulationParseResult) -> SimulationValidationResult:
        raise NotImplementedError

    def build_workdir(self, spec: ExperimentSpec) -> Path:
        root = self._settings.simulators.working_directory_root
        return stage_workdir(root, spec)

    def default_workflow(self, candidate: Candidate) -> SimulationWorkflow:
        return build_single_stage_workflow(self.build_task(candidate))

    def create_experiment_spec(
        self,
        candidate: Candidate,
        workflow: SimulationWorkflow | None = None,
        stage_name: str = "primary",
    ) -> ExperimentSpec:
        task = self.build_task(candidate)
        workflow_value = workflow or build_single_stage_workflow(task, stage_name=stage_name)
        stage = workflow_value.stage_map()[stage_name]
        spec = ExperimentSpec(
            campaign_id=candidate.campaign_id,
            candidate_id=candidate.id,
            simulator=stage.simulator,
            simulator_version=None,
            stage_name=stage.name,
            workflow_name=workflow_value.name,
            parameters={**stage.task.parameters, **candidate.values},
            units=stage.task.units,
            material=stage.task.material,
            geometry=stage.task.geometry,
            boundary_conditions=stage.task.boundary_conditions,
            mesh=stage.task.mesh,
            workflow=workflow_value,
            provenance={"candidate_values": candidate.values},
            metadata={"candidate_source": candidate.source, **candidate.metadata},
        )
        spec.workdir_path = str(self.build_workdir(spec))
        return spec

    def prepare_input(self, candidate: Candidate) -> PreparedRun:
        spec = self.create_experiment_spec(candidate)
        simulation_input = SimulationInput(
            campaign_id=candidate.campaign_id,
            candidate_id=candidate.id,
            simulator=self.simulator_kind,
            experiment_id=spec.id,
            stage_name=spec.stage_name,
            payload={
                "workflow_name": spec.workflow_name,
                "parameters": spec.parameters,
                "units": spec.units,
                "material": spec.material.model_dump(mode="json") if spec.material else None,
                "geometry": spec.geometry.model_dump(mode="json") if spec.geometry else None,
            },
            seed=int(candidate.metadata.get("seed", 42)),
            working_directory=spec.workdir_path,
        )
        command = self.build_command(spec, Path(spec.workdir_path))
        return PreparedRun(
            campaign_id=candidate.campaign_id,
            candidate_id=candidate.id,
            simulator=self.simulator_kind,
            simulation_input=simulation_input,
            experiment_spec=spec,
            command=command,
            environment=self.environment_overrides,
            metadata={
                "enabled": self.enabled,
                "workflow_name": spec.workflow_name,
                "stage_name": spec.stage_name,
            },
        )

    def run(self, prepared_run: PreparedRun) -> JobHandle:
        spec = prepared_run.experiment_spec or self.create_experiment_spec(
            Candidate(
                campaign_id=prepared_run.campaign_id,
                id=prepared_run.candidate_id,
                values={},
                metadata={},
            )
        )
        execution = self.launch(spec, Path(spec.workdir_path))
        job_id = str(execution.id)
        self._executions[job_id] = execution
        return JobHandle(
            id=job_id,
            prepared_run_id=prepared_run.id,
            simulator=self.simulator_kind,
            status=execution.status,
            metadata={
                "working_directory": execution.workdir_path,
                "experiment_id": str(execution.experiment_id),
                "stage_name": execution.stage_name,
            },
        )

    def launch(self, spec: ExperimentSpec, workdir: Path) -> SimulationExecutionRecord:
        workdir.mkdir(parents=True, exist_ok=True)
        input_artifacts = self.generate_inputs(spec, workdir)
        environment_artifact = write_json_artifact(
            path=workdir / "environment.json",
            payload=self.environment_overrides,
            artifact_type=ArtifactType.ENVIRONMENT,
            artifact_role="environment_manifest",
            stage_name=spec.stage_name,
        )
        parameters_artifact = write_json_artifact(
            path=workdir / "parameters.json",
            payload={
                "parameters": spec.parameters,
                "units": spec.units,
                "material": spec.material.model_dump(mode="json") if spec.material else None,
                "geometry": spec.geometry.model_dump(mode="json") if spec.geometry else None,
            },
            artifact_type=ArtifactType.METADATA,
            artifact_role="parameter_snapshot",
            stage_name=spec.stage_name,
        )
        command = self.build_command(spec, workdir)
        execution = SimulationExecutionRecord(
            experiment_id=spec.id,
            campaign_id=spec.campaign_id,
            candidate_id=spec.candidate_id,
            simulator=self.simulator_kind,
            stage_name=spec.stage_name,
            workdir_path=str(workdir),
            command=command,
            environment=self.environment_overrides,
            input_files=[
                artifact.path
                for artifact in [*input_artifacts, environment_artifact, parameters_artifact]
            ],
            log_files=[str(workdir / "stdout.log"), str(workdir / "stderr.log")],
            status=RunStatus.QUEUED,
            metadata={
                "input_sha256": sha256_digest(
                    stable_json_dumps(
                        {
                            "parameters": spec.parameters,
                            "units": spec.units,
                            "command": command,
                        }
                    ).encode("utf-8")
                )
            },
        )
        known_input_paths = set(execution.input_files)
        known_log_paths = set(execution.log_files)
        try:
            run_result = self._runner.run(
                command=command,
                cwd=workdir,
                stdout_path=workdir / "stdout.log",
                stderr_path=workdir / "stderr.log",
                timeout_seconds=self.timeout_seconds,
                environment=self.environment_overrides,
                wrapper=self.command_wrapper,
            )
            execution.command = run_result.command
            execution.status = (
                RunStatus.SUCCEEDED
                if run_result.exit_code == 0
                else RunStatus.TIMED_OUT
                if run_result.exit_code is None and run_result.message == "timed out"
                else RunStatus.FAILED
            )
            execution.exit_code = run_result.exit_code
            execution.started_at = run_result.started_at
            execution.ended_at = run_result.ended_at
            execution.message = run_result.message
        except BinaryNotAvailableError as exc:
            (workdir / "stdout.log").write_text("", encoding="utf-8")
            (workdir / "stderr.log").write_text(str(exc), encoding="utf-8")
            execution.status = RunStatus.FAILED
            execution.message = str(exc)
            execution.started_at = execution.ended_at = None

        execution.output_files = [
            path
            for path in list_files(workdir)
            if path not in known_input_paths and path not in known_log_paths
        ]
        execution.metadata["output_sha256"] = sha256_digest(
            stable_json_dumps(
                {"files": execution.output_files, "status": execution.status.value}
            ).encode("utf-8")
        )
        manifest_artifact = write_manifest(
            spec=spec,
            execution=execution,
            artifacts=[*input_artifacts, environment_artifact, parameters_artifact],
            workdir=workdir,
        )
        execution.input_files.append(manifest_artifact.path)
        return execution

    def poll(self, job_handle: JobHandle) -> SimulationStatus:
        execution = self._executions[job_handle.id]
        return SimulationStatus(
            job_id=job_handle.id,
            status=execution.status,
            terminal=execution.status
            in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.TIMED_OUT},
            message=execution.message,
        )

    def collect_outputs(self, execution: SimulationExecutionRecord) -> list[SimulationArtifact]:
        return [
            SimulationArtifact(
                artifact_type=ArtifactType.OUTPUT,
                artifact_role="collected_output",
                path=path,
                stage_name=execution.stage_name,
            )
            for path in execution.output_files
        ]

    def parse(self, job_handle: JobHandle) -> SimulationResult:
        execution = self._executions[job_handle.id]
        parsed = self.parse_outputs(execution)
        validation = self.validate_parsed(parsed)
        self._parse_results[job_handle.id] = parsed
        self._validation_results[job_handle.id] = validation
        parsed_summary_artifact = write_json_artifact(
            path=Path(execution.workdir_path) / "parsed_summary.json",
            payload={
                "scalar_metrics": parsed.scalar_metrics,
                "timeseries": parsed.timeseries,
                "warnings": parsed.warnings,
                "parse_errors": parsed.parse_errors,
                "convergence": parsed.convergence,
                "validation": validation.model_dump(mode="json"),
            },
            artifact_type=ArtifactType.SUMMARY,
            artifact_role="parsed_summary",
            stage_name=execution.stage_name,
        )
        output_paths = sorted({*execution.output_files, parsed_summary_artifact.path})
        execution.output_files = output_paths
        summary = (
            f"{self.simulator_name} stage {execution.stage_name} finished with status "
            f"{execution.status.value} and {len(parsed.scalar_metrics)} parsed metrics."
        )
        failure_class = validation.failure_class
        if execution.status == RunStatus.TIMED_OUT:
            failure_class = FailureClass.TIMEOUT
        elif execution.status == RunStatus.FAILED and failure_class == FailureClass.NONE:
            failure_class = FailureClass.ENGINE
        return SimulationResult(
            run_id=execution.experiment_id,
            candidate_id=execution.candidate_id,
            simulator=self.simulator_kind,
            status=execution.status,
            metrics=parsed.scalar_metrics,
            raw_outputs={
                "execution": execution.model_dump(mode="json"),
                "parse_result": parsed.model_dump(mode="json"),
                "validation_result": validation.model_dump(mode="json"),
            },
            summary=summary,
            artifact_paths=output_paths,
            failure_class=failure_class,
            execution=execution,
            parsed=parsed,
            validation=validation,
        )

    def _build_validation_report(
        self, result: SimulationResult, validation: SimulationValidationResult
    ) -> ValidationOutcome:
        return ValidationOutcome(
            report=ValidationReport(
                run_id=result.run_id,
                valid=validation.valid,
                issues=[
                    ValidationIssue(
                        code=f"{validation.stage_name}:{index}",
                        message=reason,
                    )
                    for index, reason in enumerate(validation.reasons, start=1)
                ],
                derived_metrics=validation.derived_metrics,
            ),
            metadata={
                "stage_name": validation.stage_name,
                "status": validation.status,
                "retryable": validation.retryable,
            },
        )

    def validate(self, result: SimulationResult) -> ValidationOutcome:
        validation_payload = result.raw_outputs.get("validation_result")
        if not isinstance(validation_payload, dict):
            validation = SimulationValidationResult(
                experiment_id=result.run_id,
                campaign_id=(
                    result.execution.campaign_id if result.execution else result.candidate_id
                ),
                candidate_id=result.candidate_id,
                simulator=result.simulator,
                stage_name=result.execution.stage_name if result.execution else "primary",
                status="invalid",
                reasons=["missing validation payload"],
                failure_class=FailureClass.VALIDATION,
            )
        else:
            validation = SimulationValidationResult.model_validate(validation_payload)
        return self._build_validation_report(result, validation)


__all__ = ["SimulatorAdapter", "WorkflowBackedSimulator"]
