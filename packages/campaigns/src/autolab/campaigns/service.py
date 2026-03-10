from __future__ import annotations

from typing import Any
from uuid import UUID

from autolab.campaigns.mlflow import log_run
from autolab.core.enums import ArtifactType, CampaignStatus, FailureClass, RunStatus
from autolab.core.models import (
    AgentDecision,
    ArtifactRecord,
    Campaign,
    Candidate,
    OptimizerState,
    SimulationRun,
    ValidationReport,
)
from autolab.core.settings import Settings
from autolab.core.utils import sha256_digest, stable_json_dumps
from autolab.evaluation import compute_objective_score, validate_constraints
from autolab.optimizers import BayesianOptimizer
from autolab.skills import SkillContext, get_builtin_skills
from autolab.storage import (
    ArtifactRepository,
    ArtifactStore,
    CampaignRepository,
    DecisionRepository,
    RunRepository,
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
        self._optimizer = BayesianOptimizer()
        self._skills = get_builtin_skills()
        self._artifact_store = ArtifactStore(settings)

    def create_campaign(self, campaign: Campaign) -> Campaign:
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
            previous_candidates = runs.list_candidates(campaign_id)
            previous_runs = runs.list_runs(campaign_id)
            suggested, _ = self._optimizer.suggest(
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
            artifacts = ArtifactRepository(session)
            decisions = DecisionRepository(session)
            optimizer_states = OptimizerStateRepository(session)

            campaign = campaigns.get(campaign_id)
            if campaign is None:
                msg = f"campaign {campaign_id} not found"
                raise KeyError(msg)
            if campaign.status not in {CampaignStatus.RUNNING, CampaignStatus.DRAFT}:
                msg = f"campaign {campaign_id} cannot step from status {campaign.status.value}"
                raise ValueError(msg)

            prior_candidates = runs.list_candidates(campaign_id)
            prior_runs = runs.list_runs(campaign_id)
            if len(prior_runs) >= campaign.budget.max_runs:
                campaigns.update_status(campaign_id, CampaignStatus.COMPLETED)
                return {"campaign_id": str(campaign_id), "status": "completed", "run_ids": []}

            batch, optimizer_state = self._optimizer.suggest(
                campaign,
                previous_candidates=prior_candidates,
                previous_runs=prior_runs,
                state=optimizer_states.get(campaign_id),
            )
            batch = batch[
                : min(campaign.budget.batch_size, campaign.budget.max_runs - len(prior_runs))
            ]
            decision = AgentDecision(
                campaign_id=campaign.id,
                agent_name="planner_agent",
                action="propose_batch",
                rationale="Bayesian optimizer proposed the next candidate batch.",
                structured_output={"candidate_ids": [str(candidate.id) for candidate in batch]},
            )
            decisions.create(decision)
            executed_runs: list[SimulationRun] = []
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
                executed_runs.append(
                    self._execute_run(
                        campaign, candidate, simulation_run, artifacts, runs, decisions
                    )
                )

            optimizer_states.upsert(
                OptimizerState(
                    campaign_id=campaign.id,
                    algorithm=optimizer_state.algorithm,
                    observation_count=len(
                        [run for run in executed_runs if _is_feasible_run(run)]
                    )
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
                    optimizer=self._optimizer,
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
    ) -> SimulationRun:
        simulator = self._simulator_registry.get(campaign.simulator)
        prepared = simulator.prepare_input(candidate)
        handle = simulator.run(prepared)
        simulator.poll(handle)
        result = simulator.parse(handle)
        simulator_validation = simulator.validate(result)
        simulator_report = simulator_validation.report.model_copy(update={"run_id": run.id})
        constraint_validation = validate_constraints(
            campaign.constraints,
            result.metrics,
            run_id=run.id,
        )
        validation = ValidationReport(
            run_id=run.id,
            valid=simulator_report.valid and constraint_validation.valid,
            issues=[
                *simulator_report.issues,
                *constraint_validation.issues,
            ],
            derived_metrics={
                **simulator_report.derived_metrics,
                **constraint_validation.derived_metrics,
            },
        )
        run.status = result.status
        run.failure_class = result.failure_class
        if result.status == RunStatus.SUCCEEDED and not validation.valid:
            run.failure_class = FailureClass.VALIDATION
        run.job_id = handle.id
        run.attempt += 1
        run.metrics = result.metrics
        run.metadata = {
            **run.metadata,
            "feasible": validation.valid,
            "objective_score": self._objective_score(campaign, result.metrics),
            "prepared_input": prepared.simulation_input.payload,
            "validation": validation.model_dump(mode="json"),
            "simulator_validation": simulator_report.model_dump(mode="json"),
            "constraint_validation": constraint_validation.model_dump(mode="json"),
        }
        runs.update_run(run)
        if result.artifact_paths:
            report_artifact = self._artifact_store.write_text(
                campaign.id,
                run.id,
                ArtifactType.REPORT,
                f"{run.id}/run_report.txt",
                result.summary,
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
                rationale=result.summary,
                structured_output={
                    "metrics": result.metrics,
                    "validation_passed": validation.valid,
                    "job_id": handle.id,
                },
            )
        )
        return run

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
