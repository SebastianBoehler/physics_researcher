from __future__ import annotations

from dataclasses import dataclass
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
from autolab.evaluation import compute_objective_score
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel


@dataclass(slots=True)
class _EncodedCandidate:
    vector: np.ndarray
    values: dict[str, float | int | str]


class _TopKBatchSelector:
    def select(self, scored_candidates: list[Candidate], batch_size: int) -> list[Candidate]:
        ranked = sorted(
            scored_candidates,
            key=lambda candidate: candidate.predicted_metrics.get("acquisition_score", 0.0),
            reverse=True,
        )
        return ranked[:batch_size]


class BayesianOptimizer:
    algorithm_name = "bayesian_gp"

    def __init__(self, random_seed: int = 42, candidate_pool_size: int = 32) -> None:
        self._random_seed = random_seed
        self._candidate_pool_size = candidate_pool_size
        self._batch_selector = _TopKBatchSelector()

    def suggest(
        self,
        campaign: Campaign,
        previous_candidates: list[Candidate],
        previous_runs: list[SimulationRun],
        state: OptimizerState | None,
    ) -> tuple[list[Candidate], OptimizerState]:
        rng = np.random.default_rng(campaign.seed + len(previous_runs) + self._random_seed)
        observed = self._build_observations(campaign, previous_candidates, previous_runs)
        pool = [
            self._sample_candidate(campaign, rng, batch_index=index)
            for index in range(self._candidate_pool_size)
        ]
        if len(observed["targets"]) < 3:
            selected = self._batch_selector.select(pool, campaign.budget.batch_size)
            return selected, self._build_state(campaign, observed["targets"])

        model = GaussianProcessRegressor(
            kernel=Matern(nu=2.5) + WhiteKernel(noise_level=1e-5),
            normalize_y=True,
            random_state=self._random_seed,
        )
        model.fit(np.asarray(observed["features"]), np.asarray(observed["targets"]))
        scored = []
        for candidate in pool:
            encoded = self._encode_values(campaign, candidate.values)
            mean, std = model.predict(np.asarray([encoded]), return_std=True)
            candidate.predicted_metrics = {
                "predicted_objective": float(mean[0]),
                "uncertainty": float(std[0]),
                "acquisition_score": float(mean[0] + 0.35 * std[0]),
            }
            scored.append(candidate)
        selected = self._batch_selector.select(scored, campaign.budget.batch_size)
        return selected, self._build_state(
            campaign, observed["targets"], previous_payload=state.payload if state else None
        )

    def _build_observations(
        self,
        campaign: Campaign,
        previous_candidates: list[Candidate],
        previous_runs: list[SimulationRun],
    ) -> dict[str, list[Any]]:
        candidate_map = {candidate.id: candidate for candidate in previous_candidates}
        features: list[np.ndarray] = []
        targets: list[float] = []
        for run in previous_runs:
            if not self._is_feasible_run(run):
                continue
            candidate = candidate_map.get(run.candidate_id)
            if candidate is None or not run.metrics:
                continue
            features.append(self._encode_values(campaign, candidate.values))
            targets.append(compute_objective_score(campaign.objectives, run.metrics))
        return {"features": features, "targets": targets}

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
            source="bayesian_optimizer",
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

    def _encode_values(
        self, campaign: Campaign, values: dict[str, float | int | str]
    ) -> np.ndarray:
        encoded: list[float] = []
        for dimension in campaign.search_space.dimensions:
            raw_value = values[dimension.name]
            if dimension.kind == ParameterKind.CATEGORICAL:
                encoded.append(float(dimension.choices.index(str(raw_value))))
            else:
                encoded.append(float(raw_value))
        return np.asarray(encoded)

    def _build_state(
        self,
        campaign: Campaign,
        targets: list[float],
        previous_payload: dict[str, object] | None = None,
    ) -> OptimizerState:
        payload = dict(previous_payload or {})
        payload["best_observed_objective"] = max(targets) if targets else None
        payload["feasible_observation_count"] = len(targets)
        payload["candidate_pool_size"] = self._candidate_pool_size
        return OptimizerState(
            campaign_id=campaign.id,
            algorithm=self.algorithm_name,
            observation_count=len(targets),
            payload=payload,
        )

    def _is_feasible_run(self, run: SimulationRun) -> bool:
        validation = run.metadata.get("validation", {})
        if isinstance(validation, dict) and "valid" in validation:
            return bool(validation["valid"])
        return run.status.value == "succeeded" and run.failure_class.value == "none"
