from __future__ import annotations

from statistics import mean
from typing import Any
from uuid import UUID

from autolab.core.models import Candidate, Constraint, SimulationRun
from autolab.evaluation import validate_constraints
from autolab.skills.registry import SkillContext, SkillRegistry, SkillSpec
from pydantic import BaseModel, Field


class ProposeCandidatesInput(BaseModel):
    campaign_id: UUID
    count: int = Field(ge=1)


class ProposeCandidatesOutput(BaseModel):
    candidates: list[Candidate]


class LaunchSimulationInput(BaseModel):
    candidate: Candidate
    simulator: str


class LaunchSimulationOutput(BaseModel):
    job_id: str
    status: str


class ParseSimulationResultInput(BaseModel):
    run: SimulationRun


class ParseSimulationResultOutput(BaseModel):
    summary: str
    metrics: dict[str, float]


class ValidateConstraintsInput(BaseModel):
    constraints: list[Constraint]
    metrics: dict[str, float]


class ValidateConstraintsOutput(BaseModel):
    valid: bool
    issues: list[str]


class SummarizeCampaignStateInput(BaseModel):
    runs: list[SimulationRun]


class SummarizeCampaignStateOutput(BaseModel):
    summary: str


class SelectNextBatchInput(BaseModel):
    candidates: list[Candidate]
    batch_size: int = Field(ge=1)


class SelectNextBatchOutput(BaseModel):
    selected_ids: list[UUID]


class WriteRunReportInput(BaseModel):
    run: SimulationRun


class WriteRunReportOutput(BaseModel):
    body: str


class DetectFailedRunsInput(BaseModel):
    runs: list[SimulationRun]


class DetectFailedRunsOutput(BaseModel):
    failed_run_ids: list[UUID]


class RankCandidatesInput(BaseModel):
    candidates: list[Candidate]


class RankCandidatesOutput(BaseModel):
    ordered_candidate_ids: list[UUID]


class CompareRecentExperimentsInput(BaseModel):
    runs: list[SimulationRun]


class CompareRecentExperimentsOutput(BaseModel):
    summary: str


def _propose_candidates(
    payload: ProposeCandidatesInput, context: SkillContext
) -> ProposeCandidatesOutput:
    if context.optimizer is None or context.campaign_service is None:
        return ProposeCandidatesOutput(candidates=[])
    candidates = context.campaign_service.preview_candidates(payload.campaign_id, payload.count)
    return ProposeCandidatesOutput(candidates=candidates)


def _launch_simulation(
    payload: LaunchSimulationInput, context: SkillContext
) -> LaunchSimulationOutput:
    if context.simulator_registry is None:
        return LaunchSimulationOutput(job_id="unavailable", status="registry_missing")
    simulator = context.simulator_registry.get(payload.candidate.metadata.get("simulator_kind"))
    prepared = simulator.prepare_input(payload.candidate)
    handle = simulator.run(prepared)
    return LaunchSimulationOutput(job_id=handle.id, status=handle.status.value)


def _parse_result(
    payload: ParseSimulationResultInput, _: SkillContext
) -> ParseSimulationResultOutput:
    return ParseSimulationResultOutput(summary="Parsed result payload", metrics=payload.run.metrics)


def _validate_constraints(
    payload: ValidateConstraintsInput, _: SkillContext
) -> ValidateConstraintsOutput:
    report = validate_constraints(payload.constraints, payload.metrics)
    return ValidateConstraintsOutput(
        valid=report.valid,
        issues=[issue.message for issue in report.issues],
    )


def _summarize_campaign_state(
    payload: SummarizeCampaignStateInput, _: SkillContext
) -> SummarizeCampaignStateOutput:
    total = len(payload.runs)
    completed = len([run for run in payload.runs if run.status.value == "succeeded"])
    return SummarizeCampaignStateOutput(summary=f"{completed}/{total} runs succeeded.")


def _select_next_batch(payload: SelectNextBatchInput, _: SkillContext) -> SelectNextBatchOutput:
    selected = sorted(
        payload.candidates,
        key=lambda candidate: candidate.predicted_metrics.get("acquisition_score", 0.0),
        reverse=True,
    )[: payload.batch_size]
    return SelectNextBatchOutput(selected_ids=[candidate.id for candidate in selected])


def _write_run_report(payload: WriteRunReportInput, _: SkillContext) -> WriteRunReportOutput:
    return WriteRunReportOutput(
        body=(
            f"Run {payload.run.id} finished with status {payload.run.status.value} "
            f"and metrics {payload.run.metrics}."
        )
    )


def _detect_failed_runs(payload: DetectFailedRunsInput, _: SkillContext) -> DetectFailedRunsOutput:
    failed = [run.id for run in payload.runs if run.status.value in {"failed", "timed_out"}]
    return DetectFailedRunsOutput(failed_run_ids=failed)


def _rank_candidates(payload: RankCandidatesInput, _: SkillContext) -> RankCandidatesOutput:
    ordered = sorted(
        payload.candidates,
        key=lambda candidate: candidate.predicted_metrics.get("predicted_objective", 0.0),
        reverse=True,
    )
    return RankCandidatesOutput(ordered_candidate_ids=[candidate.id for candidate in ordered])


def _compare_recent(
    payload: CompareRecentExperimentsInput, _: SkillContext
) -> CompareRecentExperimentsOutput:
    objective_values = [run.metrics.get("conductivity", 0.0) for run in payload.runs if run.metrics]
    if not objective_values:
        return CompareRecentExperimentsOutput(summary="No completed experiments to compare.")
    return CompareRecentExperimentsOutput(
        summary=(
            f"Recent mean conductivity={mean(objective_values):.3f}, "
            f"best={max(objective_values):.3f}, count={len(objective_values)}."
        )
    )


def get_builtin_skills() -> SkillRegistry:
    registry = SkillRegistry()
    skills: list[SkillSpec[Any, Any]] = [
        SkillSpec(
            "propose_candidates",
            "Propose the next candidate set for a campaign.",
            ProposeCandidatesInput,
            ProposeCandidatesOutput,
            _propose_candidates,
        ),
        SkillSpec(
            "launch_simulation",
            "Prepare and launch a simulator run for a candidate.",
            LaunchSimulationInput,
            LaunchSimulationOutput,
            _launch_simulation,
        ),
        SkillSpec(
            "parse_simulation_result",
            "Parse run metrics into a compact result payload.",
            ParseSimulationResultInput,
            ParseSimulationResultOutput,
            _parse_result,
        ),
        SkillSpec(
            "validate_constraints",
            "Validate run metrics against campaign constraints.",
            ValidateConstraintsInput,
            ValidateConstraintsOutput,
            _validate_constraints,
        ),
        SkillSpec(
            "summarize_campaign_state",
            "Summarize recent campaign progress.",
            SummarizeCampaignStateInput,
            SummarizeCampaignStateOutput,
            _summarize_campaign_state,
        ),
        SkillSpec(
            "select_next_batch",
            "Select the highest-value candidates from a candidate pool.",
            SelectNextBatchInput,
            SelectNextBatchOutput,
            _select_next_batch,
        ),
        SkillSpec(
            "write_run_report",
            "Write a compact report for a completed run.",
            WriteRunReportInput,
            WriteRunReportOutput,
            _write_run_report,
        ),
        SkillSpec(
            "detect_failed_runs",
            "Find failed or timed-out runs.",
            DetectFailedRunsInput,
            DetectFailedRunsOutput,
            _detect_failed_runs,
        ),
        SkillSpec(
            "rank_candidates",
            "Rank candidates by predicted objective.",
            RankCandidatesInput,
            RankCandidatesOutput,
            _rank_candidates,
        ),
        SkillSpec(
            "compare_recent_experiments",
            "Compare metrics across recent runs.",
            CompareRecentExperimentsInput,
            CompareRecentExperimentsOutput,
            _compare_recent,
        ),
    ]
    for skill in skills:
        registry.register(skill)
    return registry
