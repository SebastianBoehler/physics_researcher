from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import UUID

from autolab.campaigns.mlflow import log_run
from autolab.campaigns.stage_mapping import build_stage_mapping_registry
from autolab.campaigns.workflow_graph import resolve_campaign_workflow, stage_order
from autolab.core.enums import ArtifactType, CampaignStatus, FailureClass, RunStatus
from autolab.core.models import (
    AgentDecision,
    ArtifactRecord,
    Campaign,
    Candidate,
    OptimizerState,
    SimulationExecutionRecord,
    SimulationInput,
    SimulationRun,
    ValidationIssue,
    ValidationReport,
)
from autolab.core.settings import Settings
from autolab.core.utils import sha256_digest, stable_json_dumps
from autolab.evaluation import compute_objective_score, validate_constraints
from autolab.optimizers import build_optimizer
from autolab.simulators.types import PreparedRun
from autolab.skills import SkillContext, get_builtin_skills
from autolab.storage import (
    ArtifactRepository,
    ArtifactStore,
    CampaignRepository,
    DecisionRepository,
    RunRepository,
    SimulatorProvenanceRepository,
    StageExecutionRepository,
)
from autolab.storage.db import session_scope
from autolab.storage.repositories import OptimizerStateRepository
from autolab.telemetry import get_logger

logger = get_logger(__name__)


def _is_feasible_run(run: SimulationRun) -> bool:
    validation = run.metadata.get("validation", {})
    if isinstance(validation, dict) and "valid" in validation:
        return bool(validation["valid"])
    return run.status == RunStatus.SUCCEEDED and run.failure_class == FailureClass.NONE


class CampaignService:
    def __init__(self, settings: Settings, simulator_registry: Any) -> None:
        self._settings = settings
        self._simulator_registry = simulator_registry
        self._skills = get_builtin_skills()
        self._artifact_store = ArtifactStore(settings)
        self._stage_mappings = build_stage_mapping_registry()

    def create_campaign(self, campaign: Campaign) -> Campaign:
        self._resolve_optimizer(campaign)
        snapshot = self._settings.snapshot()
        snapshot_digest = sha256_digest(stable_json_dumps(snapshot).encode("utf-8"))
        with session_scope(self._settings) as session:
            campaigns = CampaignRepository(session)
            campaigns.create(campaign)
            campaigns.save_config_snapshot(campaign.id, snapshot_digest, snapshot)
        return campaign

    def get_campaign(self, campaign_id: UUID) -> Campaign | None:
        with session_scope(self._settings) as session:
            return CampaignRepository(session).get(campaign_id)

    def start_campaign(self, campaign_id: UUID) -> Campaign:
        with session_scope(self._settings) as session:
            return CampaignRepository(session).update_status(campaign_id, CampaignStatus.RUNNING)

    def stop_campaign(self, campaign_id: UUID) -> Campaign:
        with session_scope(self._settings) as session:
            return CampaignRepository(session).update_status(campaign_id, CampaignStatus.PAUSED)

    def preview_candidates(self, campaign_id: UUID, count: int) -> list[Candidate]:
        with session_scope(self._settings) as session:
            campaigns = CampaignRepository(session)
            runs = RunRepository(session)
            optimizer_state_repo = OptimizerStateRepository(session)
            campaign = campaigns.get(campaign_id)
            if campaign is None:
                return []
            optimizer = self._resolve_optimizer(campaign)
            previous_candidates = runs.list_candidates(campaign_id)
            previous_runs = runs.list_runs(campaign_id)
            suggested, _ = optimizer.suggest(
                campaign,
                previous_candidates=previous_candidates,
                previous_runs=previous_runs,
                state=optimizer_state_repo.get(campaign_id),
            )
            return suggested[:count]

    def step_campaign(self, campaign_id: UUID) -> dict[str, Any]:
        with session_scope(self._settings) as session:
            campaigns = CampaignRepository(session)
            runs = RunRepository(session)
            decisions = DecisionRepository(session)
            optimizer_states = OptimizerStateRepository(session)

            campaign = campaigns.get(campaign_id)
            if campaign is None:
                msg = f"campaign {campaign_id} not found"
                raise KeyError(msg)
            if campaign.status not in {CampaignStatus.RUNNING, CampaignStatus.DRAFT}:
                msg = f"campaign {campaign_id} cannot step from status {campaign.status.value}"
                raise ValueError(msg)
            optimizer = self._resolve_optimizer(campaign)

            prior_candidates = runs.list_candidates(campaign_id)
            prior_runs = runs.list_runs(campaign_id)
            if len(prior_runs) >= campaign.budget.max_runs:
                campaigns.update_status(campaign_id, CampaignStatus.COMPLETED)
                return {"campaign_id": str(campaign_id), "status": "completed", "run_ids": []}

            batch, optimizer_state = optimizer.suggest(
                campaign,
                previous_candidates=prior_candidates,
                previous_runs=prior_runs,
                state=optimizer_states.get(campaign_id),
            )
            batch = batch[
                : min(campaign.budget.batch_size, campaign.budget.max_runs - len(prior_runs))
            ]
            decisions.create(
                AgentDecision(
                    campaign_id=campaign.id,
                    agent_name="planner_agent",
                    action="propose_batch",
                    rationale=(
                        f"{optimizer.algorithm_name} proposed the next candidate batch."
                    ),
                    structured_output={"candidate_ids": [str(candidate.id) for candidate in batch]},
                )
            )
            scheduled_runs: list[tuple[Candidate, SimulationRun]] = []
            for candidate in batch:
                candidate.metadata["simulator_kind"] = campaign.simulator
                runs.create_candidate(candidate)
                simulation_run = SimulationRun(
                    campaign_id=campaign.id,
                    candidate_id=candidate.id,
                    simulator=campaign.simulator,
                    status=RunStatus.PENDING,
                    failure_class=FailureClass.NONE,
                    metadata={"seed": campaign.seed, "candidate_values": candidate.values},
                )
                runs.create_run(simulation_run)
                scheduled_runs.append((candidate, simulation_run))

        executed_runs = self._execute_batch_runs(campaign, scheduled_runs)

        with session_scope(self._settings) as session:
            campaigns = CampaignRepository(session)
            runs = RunRepository(session)
            decisions = DecisionRepository(session)
            optimizer_states = OptimizerStateRepository(session)
            prior_runs = runs.list_runs(campaign_id)

            optimizer_states.upsert(
                OptimizerState(
                    campaign_id=campaign.id,
                    algorithm=optimizer_state.algorithm,
                    observation_count=len([run for run in executed_runs if _is_feasible_run(run)])
                    + len([run for run in prior_runs if _is_feasible_run(run)]),
                    payload=optimizer_state.payload,
                )
            )

            completed_runs = runs.list_runs(campaign_id)
            summary_skill = self._skills.get("compare_recent_experiments")
            summary = summary_skill.run(
                summary_skill.input_model(runs=completed_runs[-5:]),
                SkillContext(
                    campaign_service=self,
                    optimizer=optimizer,
                    simulator_registry=self._simulator_registry,
                ),
            )
            campaigns.save_summary(campaign_id, "critic", summary.summary, None)
            decisions.create(
                AgentDecision(
                    campaign_id=campaign.id,
                    agent_name="critic_agent",
                    action="summarize_recent_runs",
                    rationale=summary.summary,
                    structured_output={"run_count": len(completed_runs)},
                )
            )

            if len(completed_runs) >= campaign.budget.max_runs:
                final_campaign = campaigns.update_status(campaign_id, CampaignStatus.COMPLETED)
            else:
                final_campaign = campaigns.update_status(campaign_id, CampaignStatus.RUNNING)

            return {
                "campaign_id": str(campaign_id),
                "status": final_campaign.status.value,
                "run_ids": [str(run.id) for run in executed_runs],
            }

    def _resolve_optimizer(self, campaign: Campaign) -> Any:
        return build_optimizer(campaign.metadata)

    def _execute_batch_runs(
        self,
        campaign: Campaign,
        scheduled_runs: list[tuple[Candidate, SimulationRun]],
    ) -> list[SimulationRun]:
        if not scheduled_runs:
            return []
        max_workers = min(
            len(scheduled_runs),
            max(1, self._settings.app.max_parallel_runs),
            max(1, campaign.budget.batch_size),
        )
        if max_workers == 1:
            return [
                self._execute_run_in_isolated_session(campaign, candidate, run)
                for candidate, run in scheduled_runs
            ]
        results: list[SimulationRun | None] = [None] * len(scheduled_runs)
        with ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=f"autolab-{campaign.id}-run",
        ) as executor:
            future_map = {
                executor.submit(
                    self._execute_run_in_isolated_session,
                    campaign,
                    candidate,
                    run,
                ): index
                for index, (candidate, run) in enumerate(scheduled_runs)
            }
            for future, index in future_map.items():
                try:
                    results[index] = future.result()
                except Exception as exc:
                    logger.exception(
                        "Parallel run execution failed for campaign %s run %s",
                        campaign.id,
                        scheduled_runs[index][1].id,
                    )
                    results[index] = self._mark_run_failed_in_isolated_session(
                        campaign=campaign,
                        run=scheduled_runs[index][1],
                        error=exc,
                    )
        return [run for run in results if run is not None]

    def _execute_run_in_isolated_session(
        self,
        campaign: Campaign,
        candidate: Candidate,
        run: SimulationRun,
    ) -> SimulationRun:
        with session_scope(self._settings) as session:
            return self._execute_run(
                campaign,
                candidate,
                run,
                ArtifactRepository(session),
                RunRepository(session),
                DecisionRepository(session),
                StageExecutionRepository(session),
                SimulatorProvenanceRepository(session),
            )

    def _mark_run_failed_in_isolated_session(
        self,
        *,
        campaign: Campaign,
        run: SimulationRun,
        error: Exception,
    ) -> SimulationRun:
        with session_scope(self._settings) as session:
            runs = RunRepository(session)
            decisions = DecisionRepository(session)
            run.status = RunStatus.FAILED
            run.failure_class = FailureClass.UNKNOWN
            run.attempt += 1
            run.metadata = {
                **run.metadata,
                "feasible": False,
                "execution_error": str(error),
            }
            runs.update_run(run)
            decisions.create(
                AgentDecision(
                    campaign_id=campaign.id,
                    run_id=run.id,
                    agent_name="analysis_agent",
                    action="record_execution_failure",
                    rationale=str(error),
                    structured_output={"error": str(error)},
                )
            )
            return run

    def list_runs(self, campaign_id: UUID) -> list[SimulationRun]:
        with session_scope(self._settings) as session:
            return RunRepository(session).list_runs(campaign_id)

    def get_run(self, run_id: UUID) -> SimulationRun | None:
        with session_scope(self._settings) as session:
            return RunRepository(session).get_run(run_id)

    def get_artifact(self, artifact_id: UUID) -> ArtifactRecord | None:
        with session_scope(self._settings) as session:
            return ArtifactRepository(session).get(artifact_id)

    def _execute_run(
        self,
        campaign: Campaign,
        candidate: Candidate,
        run: SimulationRun,
        artifacts: ArtifactRepository,
        runs: RunRepository,
        decisions: DecisionRepository,
        stage_executions: StageExecutionRepository,
        simulator_provenance: SimulatorProvenanceRepository,
    ) -> SimulationRun:
        return self._execute_workflow_run(
            campaign,
            candidate,
            run,
            artifacts,
            runs,
            decisions,
            stage_executions,
            simulator_provenance,
        )

    def _execute_workflow_run(
        self,
        campaign: Campaign,
        candidate: Candidate,
        run: SimulationRun,
        artifacts: ArtifactRepository,
        runs: RunRepository,
        decisions: DecisionRepository,
        stage_executions: StageExecutionRepository,
        simulator_provenance: SimulatorProvenanceRepository,
    ) -> SimulationRun:
        workflow = resolve_campaign_workflow(campaign, candidate, self._simulator_registry)
        workflow_results: dict[str, dict[str, object]] = {}
        final_result = None

        for stage in stage_order(workflow):
            backend = self._simulator_registry.get(stage.simulator)
            spec = backend.create_experiment_spec(
                candidate,
                workflow=workflow,
                stage_name=stage.name,
            )
            spec.id = run.id
            spec.workflow_name = workflow.name
            spec.provenance.update(
                {
                    "campaign_name": campaign.name,
                    "run_id": str(run.id),
                    "stage_dependencies": stage.depends_on,
                }
            )
            for dependency in stage.depends_on:
                dependency_stage = workflow.stage_map()[dependency]
                default_mapping_name = (
                    f"{dependency_stage.simulator.value}_to_{stage.simulator.value}"
                )
                mapper = self._stage_mappings.get(stage.mapping_id or default_mapping_name)
                if mapper is None:
                    continue
                dependency_result = workflow_results[dependency]["parsed"]
                mapped_parameters = mapper(spec, dependency_result, stage)
                spec.parameters.update(mapped_parameters)
                spec.provenance.setdefault("mapped_inputs", {})[dependency] = mapped_parameters
            spec.workdir_path = str(backend.build_workdir(spec))
            prepared = PreparedRun(
                campaign_id=campaign.id,
                candidate_id=candidate.id,
                simulator=stage.simulator,
                simulation_input=SimulationInput(
                    campaign_id=campaign.id,
                    candidate_id=candidate.id,
                    simulator=stage.simulator,
                    experiment_id=spec.id,
                    stage_name=stage.name,
                    payload={
                        "workflow_name": workflow.name,
                        "parameters": spec.parameters,
                        "units": spec.units,
                    },
                    seed=campaign.seed,
                    working_directory=spec.workdir_path,
                ),
                experiment_spec=spec,
                command=backend.build_command(spec, Path(spec.workdir_path)),
                environment=backend.environment_overrides,
                metadata={"workflow_name": workflow.name, "stage_name": stage.name},
            )
            handle = backend.run(prepared)
            backend.poll(handle)
            final_result = backend.parse(handle)
            validation_outcome = backend.validate(final_result)
            execution = final_result.execution
            if execution is not None:
                stage_executions.create(execution)
                simulator_provenance.create(
                    run_id=run.id,
                    simulator=stage.simulator,
                    adapter_version=getattr(backend, "adapter_version", "0.1.0"),
                    input_sha256=str(execution.metadata.get("input_sha256", "")),
                    output_sha256=(
                        str(execution.metadata.get("output_sha256"))
                        if execution.metadata.get("output_sha256") is not None
                        else None
                    ),
                    payload={
                        "stage_name": stage.name,
                        "workflow_name": workflow.name,
                        "execution": execution.model_dump(mode="json"),
                    },
                )
                self._record_stage_artifacts(
                    campaign_id=campaign.id,
                    run_id=run.id,
                    execution=execution,
                    repository=artifacts,
                )
            workflow_results[stage.name] = {
                "result": final_result,
                "parsed": final_result.parsed,
                "validation": validation_outcome,
            }
            if not validation_outcome.report.valid or final_result.status != RunStatus.SUCCEEDED:
                break

        if final_result is None:
            msg = "workflow produced no stage results"
            raise RuntimeError(msg)

        constraint_validation = validate_constraints(
            campaign.constraints,
            final_result.metrics,
            run_id=run.id,
        )
        simulation_validation = final_result.validation
        combined_valid = (
            simulation_validation.valid if simulation_validation is not None else False
        ) and constraint_validation.valid
        validation = ValidationReport(
            run_id=run.id,
            valid=combined_valid,
            issues=[
                *[
                    ValidationIssue(code=f"stage:{index}", message=reason)
                    for index, reason in enumerate(
                        simulation_validation.reasons if simulation_validation else [],
                        start=1,
                    )
                ],
                *constraint_validation.issues,
            ],
            derived_metrics={
                **(simulation_validation.derived_metrics if simulation_validation else {}),
                **constraint_validation.derived_metrics,
            },
        )
        run.status = final_result.status
        run.failure_class = final_result.failure_class
        if final_result.status == RunStatus.SUCCEEDED and not validation.valid:
            run.failure_class = FailureClass.VALIDATION
        run.job_id = (
            str(final_result.execution.id) if final_result.execution is not None else run.job_id
        )
        run.attempt += 1
        run.metrics = final_result.metrics
        run.metadata = {
            **run.metadata,
            "feasible": validation.valid,
            "objective_score": self._objective_score(campaign, final_result.metrics),
            "workflow_name": workflow.name,
            "workflow_stage_order": [stage.name for stage in stage_order(workflow)],
            "stage_results": {
                stage_name: {
                    "status": payload["result"].status.value,
                    "metrics": payload["result"].metrics,
                    "validation": payload["validation"].report.model_dump(mode="json"),
                }
                for stage_name, payload in workflow_results.items()
            },
            "validation": validation.model_dump(mode="json"),
            "simulator_validation": (
                final_result.validation.model_dump(mode="json")
                if final_result.validation is not None
                else {}
            ),
            "constraint_validation": constraint_validation.model_dump(mode="json"),
        }
        runs.update_run(run)
        if final_result.summary:
            report_artifact = self._artifact_store.write_text(
                campaign.id,
                run.id,
                ArtifactType.REPORT,
                f"{run.id}/run_report.txt",
                final_result.summary,
                media_type="text/plain",
            )
            artifacts.create(report_artifact)
        log_run(self._settings, campaign, run)
        decisions.create(
            AgentDecision(
                campaign_id=campaign.id,
                run_id=run.id,
                agent_name="analysis_agent",
                action="parse_and_validate",
                rationale=final_result.summary,
                structured_output={
                    "metrics": final_result.metrics,
                    "validation_passed": validation.valid,
                    "job_id": run.job_id,
                    "workflow_name": workflow.name,
                },
            )
        )
        return run

    def _record_stage_artifacts(
        self,
        campaign_id: UUID,
        run_id: UUID,
        execution: SimulationExecutionRecord,
        repository: ArtifactRepository,
    ) -> None:
        artifact_paths = {
            *execution.input_files,
            *execution.output_files,
            *execution.log_files,
        }
        for artifact_path in sorted(artifact_paths):
            path = Path(artifact_path)
            if not path.exists() or not path.is_file():
                continue
            repository.create(
                self._artifact_store.record_path(
                    campaign_id=campaign_id,
                    run_id=run_id,
                    artifact_type=self._artifact_type_for_path(path),
                    path=path,
                    media_type=self._media_type_for_path(path),
                    metadata={
                        "experiment_id": str(execution.experiment_id),
                        "stage_name": execution.stage_name,
                        "artifact_role": path.stem,
                    },
                )
            )

    def _artifact_type_for_path(self, path: Path) -> ArtifactType:
        if path.name == "manifest.json":
            return ArtifactType.MANIFEST
        if path.name == "environment.json":
            return ArtifactType.ENVIRONMENT
        if path.name == "parameters.json":
            return ArtifactType.METADATA
        if path.suffix == ".log":
            return ArtifactType.LOG
        if path.suffix in {".py", ".sh"}:
            return ArtifactType.SCRIPT
        if path.name == "parsed_summary.json":
            return ArtifactType.SUMMARY
        if path.suffix in {".in", ".sif"}:
            return ArtifactType.INPUT
        return ArtifactType.OUTPUT

    def _media_type_for_path(self, path: Path) -> str:
        if path.suffix == ".json":
            return "application/json"
        if path.suffix in {".log", ".txt", ".in", ".sif", ".sh", ".py"}:
            return "text/plain"
        return "application/octet-stream"

    def _objective_score(self, campaign: Campaign, metrics: dict[str, float]) -> float:
        return compute_objective_score(campaign.objectives, metrics)


class RunService:
    def __init__(self, campaign_service: CampaignService) -> None:
        self._campaign_service = campaign_service

    def list_runs(self, campaign_id: UUID) -> list[SimulationRun]:
        return self._campaign_service.list_runs(campaign_id)

    def get_run(self, run_id: UUID) -> SimulationRun | None:
        return self._campaign_service.get_run(run_id)


class ArtifactService:
    def __init__(self, campaign_service: CampaignService) -> None:
        self._campaign_service = campaign_service

    def get_artifact(self, artifact_id: UUID) -> ArtifactRecord | None:
        return self._campaign_service.get_artifact(artifact_id)
