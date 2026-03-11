from __future__ import annotations

from typing import Any
from uuid import uuid4

import numpy as np
from autolab.core.enums import ParameterKind
from autolab.core.models import (
    Campaign,
    Candidate,
    OptimizerState,
    SearchSpaceDimension,
    SimulationRun,
)


class RandomSearchOptimizer:
    algorithm_name = "random_search"

    def __init__(self, random_seed: int = 42) -> None:
        self._random_seed = random_seed

    def suggest(
        self,
        campaign: Campaign,
        previous_candidates: list[Candidate],
        previous_runs: list[SimulationRun],
        state: OptimizerState | None,
    ) -> tuple[list[Candidate], OptimizerState]:
        del previous_candidates
        del state
        rng = np.random.default_rng(campaign.seed + len(previous_runs) + self._random_seed)
        batch = [
            self._sample_candidate(campaign, rng, batch_index=index)
            for index in range(campaign.budget.batch_size)
        ]
        return batch, self._build_state(campaign)

    def _sample_candidate(
        self, campaign: Campaign, rng: np.random.Generator, batch_index: int
    ) -> Candidate:
        values: dict[str, float | int | str] = {}
        for dimension in campaign.search_space.dimensions:
            values[dimension.name] = self._sample_dimension(dimension, rng)
        return Candidate(
            id=uuid4(),
            campaign_id=campaign.id,
            values=values,
            batch_index=batch_index,
            source="random_search_optimizer",
            metadata={"seed": campaign.seed},
        )

    def _sample_dimension(
        self, dimension: SearchSpaceDimension, rng: np.random.Generator
    ) -> float | int | str:
        if dimension.kind == ParameterKind.CATEGORICAL:
            return str(rng.choice(dimension.choices))
        if dimension.kind == ParameterKind.INTEGER:
            lower = int(dimension.lower or 0)
            upper = int(dimension.upper or 1)
            return int(rng.integers(lower, upper + 1))
        continuous_lower = float(dimension.lower or 0.0)
        continuous_upper = float(dimension.upper or 1.0)
        return round(float(rng.uniform(continuous_lower, continuous_upper)), 5)

    def _build_state(self, campaign: Campaign) -> OptimizerState:
        payload: dict[str, Any] = {
            "random_seed": self._random_seed,
            "batch_size": campaign.budget.batch_size,
        }
        return OptimizerState(
            campaign_id=campaign.id,
            algorithm=self.algorithm_name,
            observation_count=0,
            payload=payload,
        )
