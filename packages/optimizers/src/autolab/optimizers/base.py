from __future__ import annotations

from typing import Protocol

from autolab.core.models import Campaign, Candidate, OptimizerState, SimulationRun


class Optimizer(Protocol):
    algorithm_name: str

    def suggest(
        self,
        campaign: Campaign,
        previous_candidates: list[Candidate],
        previous_runs: list[SimulationRun],
        state: OptimizerState | None,
    ) -> tuple[list[Candidate], OptimizerState]: ...


class BatchSelector(Protocol):
    def select(self, scored_candidates: list[Candidate], batch_size: int) -> list[Candidate]: ...


class RLPolicy(Protocol):
    def next_action(self, state: dict[str, object]) -> dict[str, object]: ...
