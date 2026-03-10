from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from autolab.core.models import (
    ExperimentSpec,
    SimulationExecutionRecord,
    SimulationParseResult,
    SimulationStage,
    SimulationTask,
    SimulationValidationResult,
    SimulationWorkflow,
)

StageMapping = Callable[[ExperimentSpec, SimulationParseResult, SimulationStage], dict[str, Any]]


class StageMappingRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, StageMapping] = {}

    def register(self, name: str, mapper: StageMapping) -> None:
        self._registry[name] = mapper

    def get(self, name: str | None) -> StageMapping | None:
        if name is None:
            return None
        return self._registry.get(name)


def build_single_stage_workflow(
    task: SimulationTask, stage_name: str = "primary"
) -> SimulationWorkflow:
    return SimulationWorkflow(
        name=f"{task.simulator.value}-workflow",
        stages=[
            SimulationStage(
                name=stage_name,
                simulator=task.simulator,
                task=task,
            )
        ],
    )


def stage_workdir(root: Path, spec: ExperimentSpec) -> Path:
    return root / str(spec.campaign_id) / str(spec.id) / spec.stage_name


class WorkflowExecutionSummary:
    def __init__(
        self,
        executions: list[SimulationExecutionRecord],
        parse_results: list[SimulationParseResult],
        validations: list[SimulationValidationResult],
    ) -> None:
        self.executions = executions
        self.parse_results = parse_results
        self.validations = validations
