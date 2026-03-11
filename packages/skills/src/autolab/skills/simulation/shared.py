from __future__ import annotations

from pathlib import Path
from typing import Any

from autolab.core.enums import SimulatorKind
from autolab.core.models import (
    Candidate,
    ExperimentSpec,
    SimulationArtifact,
    SimulationExecutionRecord,
    SimulationParseResult,
    SimulationStage,
    SimulationValidationResult,
    SimulationWorkflow,
)
from autolab.skills.registry import SkillContext, SkillSpec
from pydantic import BaseModel


def _backend(kind: SimulatorKind, context: SkillContext) -> Any:
    if context.simulator_registry is None:
        msg = "simulator registry is unavailable"
        raise RuntimeError(msg)
    return context.simulator_registry.get(kind)


class CreateExperimentSpecInput(BaseModel):
    candidate: Candidate
    simulator: SimulatorKind
    workflow: SimulationWorkflow | None = None
    stage_name: str = "primary"


class CreateExperimentSpecOutput(BaseModel):
    spec: ExperimentSpec


class SelectSimulatorWorkflowInput(BaseModel):
    candidate: Candidate
    simulator: SimulatorKind


class SelectSimulatorWorkflowOutput(BaseModel):
    workflow: SimulationWorkflow


class GenerateSimulationArtifactsInput(BaseModel):
    spec: ExperimentSpec


class GenerateSimulationArtifactsOutput(BaseModel):
    workdir: str
    artifacts: list[SimulationArtifact]


class LaunchSimulationStageInput(BaseModel):
    spec: ExperimentSpec


class LaunchSimulationStageOutput(BaseModel):
    execution: SimulationExecutionRecord


class PollSimulationStageInput(BaseModel):
    execution: SimulationExecutionRecord


class PollSimulationStageOutput(BaseModel):
    execution: SimulationExecutionRecord


class ParseSimulationStageInput(BaseModel):
    execution: SimulationExecutionRecord


class ParseSimulationStageOutput(BaseModel):
    parsed: SimulationParseResult


class ValidateSimulationStageInput(BaseModel):
    parsed: SimulationParseResult


class ValidateSimulationStageOutput(BaseModel):
    validation: SimulationValidationResult


class CollectStageSummaryInput(BaseModel):
    execution: SimulationExecutionRecord
    parsed: SimulationParseResult
    validation: SimulationValidationResult


class CollectStageSummaryOutput(BaseModel):
    summary: str
    metrics: dict[str, float]


class StoreSimulationArtifactsInput(BaseModel):
    execution: SimulationExecutionRecord


class StoreSimulationArtifactsOutput(BaseModel):
    artifact_paths: list[str]


class LinkStageOutputsToNextStageInput(BaseModel):
    parsed: SimulationParseResult
    next_stage: SimulationStage
    base_spec: ExperimentSpec


class LinkStageOutputsToNextStageOutput(BaseModel):
    linked_spec: ExperimentSpec
    mapped_parameters: dict[str, Any]


def _create_experiment_spec(
    payload: CreateExperimentSpecInput, context: SkillContext
) -> CreateExperimentSpecOutput:
    backend = _backend(payload.simulator, context)
    return CreateExperimentSpecOutput(
        spec=backend.create_experiment_spec(
            payload.candidate,
            workflow=payload.workflow,
            stage_name=payload.stage_name,
        )
    )


def _select_simulator_workflow(
    payload: SelectSimulatorWorkflowInput, context: SkillContext
) -> SelectSimulatorWorkflowOutput:
    backend = _backend(payload.simulator, context)
    return SelectSimulatorWorkflowOutput(workflow=backend.default_workflow(payload.candidate))


def _generate_simulation_artifacts(
    payload: GenerateSimulationArtifactsInput, context: SkillContext
) -> GenerateSimulationArtifactsOutput:
    backend = _backend(payload.spec.simulator, context)
    workdir = Path(payload.spec.workdir_path or backend.build_workdir(payload.spec))
    artifacts = backend.generate_inputs(payload.spec, workdir)
    return GenerateSimulationArtifactsOutput(workdir=str(workdir), artifacts=artifacts)


def _launch_simulation_stage(
    payload: LaunchSimulationStageInput, context: SkillContext
) -> LaunchSimulationStageOutput:
    backend = _backend(payload.spec.simulator, context)
    workdir = Path(payload.spec.workdir_path or backend.build_workdir(payload.spec))
    return LaunchSimulationStageOutput(execution=backend.launch(payload.spec, workdir))


def _poll_simulation_stage(
    payload: PollSimulationStageInput, _: SkillContext
) -> PollSimulationStageOutput:
    return PollSimulationStageOutput(execution=payload.execution)


def _parse_simulation_stage(
    payload: ParseSimulationStageInput, context: SkillContext
) -> ParseSimulationStageOutput:
    backend = _backend(payload.execution.simulator, context)
    return ParseSimulationStageOutput(parsed=backend.parse_outputs(payload.execution))


def _validate_simulation_stage(
    payload: ValidateSimulationStageInput, context: SkillContext
) -> ValidateSimulationStageOutput:
    backend = _backend(payload.parsed.simulator, context)
    return ValidateSimulationStageOutput(validation=backend.validate_parsed(payload.parsed))


def _collect_stage_summary(
    payload: CollectStageSummaryInput, _: SkillContext
) -> CollectStageSummaryOutput:
    return CollectStageSummaryOutput(
        summary=(
            f"{payload.execution.simulator.value}:{payload.execution.stage_name} "
            f"status={payload.execution.status.value} "
            f"validation={payload.validation.status}"
        ),
        metrics=payload.parsed.scalar_metrics,
    )


def _store_simulation_artifacts(
    payload: StoreSimulationArtifactsInput, _: SkillContext
) -> StoreSimulationArtifactsOutput:
    artifact_paths = sorted(
        {
            *payload.execution.input_files,
            *payload.execution.output_files,
            *payload.execution.log_files,
        }
    )
    return StoreSimulationArtifactsOutput(artifact_paths=artifact_paths)


def _link_stage_outputs_to_next_stage(
    payload: LinkStageOutputsToNextStageInput, _: SkillContext
) -> LinkStageOutputsToNextStageOutput:
    mapped = {f"upstream_{key}": value for key, value in payload.parsed.scalar_metrics.items()}
    linked_spec = payload.base_spec.model_copy(
        update={
            "stage_name": payload.next_stage.name,
            "simulator": payload.next_stage.simulator,
            "parameters": {
                **payload.base_spec.parameters,
                **payload.next_stage.task.parameters,
                **mapped,
            },
        }
    )
    return LinkStageOutputsToNextStageOutput(linked_spec=linked_spec, mapped_parameters=mapped)


def get_simulation_skill_specs() -> list[SkillSpec[Any, Any]]:
    return [
        SkillSpec(
            "create_experiment_spec",
            "Create a typed experiment specification for a simulator stage.",
            CreateExperimentSpecInput,
            CreateExperimentSpecOutput,
            _create_experiment_spec,
            domain="simulation",
            tags=["workflow", "spec"],
            required_context=["simulator_registry"],
        ),
        SkillSpec(
            "select_simulator_workflow",
            "Select the default typed workflow for a simulator and candidate.",
            SelectSimulatorWorkflowInput,
            SelectSimulatorWorkflowOutput,
            _select_simulator_workflow,
            domain="simulation",
            tags=["workflow", "planning"],
            required_context=["simulator_registry"],
        ),
        SkillSpec(
            "generate_simulation_artifacts",
            "Generate simulator-specific input artifacts for a stage.",
            GenerateSimulationArtifactsInput,
            GenerateSimulationArtifactsOutput,
            _generate_simulation_artifacts,
            domain="simulation",
            tags=["artifacts", "generation"],
            required_context=["simulator_registry"],
        ),
        SkillSpec(
            "launch_simulation_stage",
            "Launch a simulator stage through the adapter layer.",
            LaunchSimulationStageInput,
            LaunchSimulationStageOutput,
            _launch_simulation_stage,
            domain="simulation",
            tags=["execution", "workflow"],
            required_context=["simulator_registry"],
        ),
        SkillSpec(
            "poll_simulation_stage",
            "Return the latest known stage execution state.",
            PollSimulationStageInput,
            PollSimulationStageOutput,
            _poll_simulation_stage,
            domain="simulation",
            tags=["execution", "status"],
        ),
        SkillSpec(
            "parse_simulation_stage",
            "Parse raw simulator outputs into normalized typed data.",
            ParseSimulationStageInput,
            ParseSimulationStageOutput,
            _parse_simulation_stage,
            domain="simulation",
            tags=["parsing", "metrics"],
            required_context=["simulator_registry"],
        ),
        SkillSpec(
            "validate_simulation_stage",
            "Validate parsed simulator outputs for completeness and plausibility.",
            ValidateSimulationStageInput,
            ValidateSimulationStageOutput,
            _validate_simulation_stage,
            domain="simulation",
            tags=["validation", "workflow"],
            required_context=["simulator_registry"],
        ),
        SkillSpec(
            "collect_stage_summary",
            "Collect a compact stage summary from execution, parse, and validation data.",
            CollectStageSummaryInput,
            CollectStageSummaryOutput,
            _collect_stage_summary,
            domain="simulation",
            tags=["summary", "workflow"],
        ),
        SkillSpec(
            "store_simulation_artifacts",
            "Collect the artifact paths produced by a simulation stage.",
            StoreSimulationArtifactsInput,
            StoreSimulationArtifactsOutput,
            _store_simulation_artifacts,
            domain="simulation",
            tags=["artifacts", "workflow"],
        ),
        SkillSpec(
            "link_stage_outputs_to_next_stage",
            "Map typed stage outputs into the next stage specification.",
            LinkStageOutputsToNextStageInput,
            LinkStageOutputsToNextStageOutput,
            _link_stage_outputs_to_next_stage,
            domain="simulation",
            tags=["mapping", "workflow"],
        ),
    ]
