from __future__ import annotations

from typing import Any
from uuid import uuid4

import numpy as np
from autolab.core.enums import ParameterKind
from autolab.core.models import Campaign, Candidate, OptimizerState, SearchSpaceDimension, SimulationRun
from autolab.evaluation import compute_objective_score
from autolab.optimizers.bayesian import BayesianOptimizer
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel


class CoarseToFineBayesianOptimizer(BayesianOptimizer):
    algorithm_name = "coarse_to_fine_bayesian"

    def __init__(
        self,
        random_seed: int = 42,
        candidate_pool_size: int = 48,
        coarse_observation_count: int = 6,
        top_candidate_count: int = 3,
        minimum_window_fraction: float = 0.2,
        padding_fraction: float = 0.08,
    ) -> None:
        super().__init__(random_seed=random_seed, candidate_pool_size=candidate_pool_size)
        self._coarse_observation_count = coarse_observation_count
        self._top_candidate_count = top_candidate_count
        self._minimum_window_fraction = minimum_window_fraction
        self._padding_fraction = padding_fraction

    def suggest(
        self,
        campaign: Campaign,
        previous_candidates: list[Candidate],
        previous_runs: list[SimulationRun],
        state: OptimizerState | None,
    ) -> tuple[list[Candidate], OptimizerState]:
        rng = np.random.default_rng(campaign.seed + len(previous_runs) + self._random_seed)
        observed = self._build_observations(campaign, previous_candidates, previous_runs)
        active_bounds = self._build_active_bounds(
            campaign, previous_candidates, previous_runs, observed["targets"]
        )
        stage_name = "refine" if active_bounds else "coarse"
        pool = [
            self._sample_candidate_with_bounds(
                campaign, rng, batch_index=index, active_bounds=active_bounds, stage_name=stage_name
            )
            for index in range(self._candidate_pool_size)
        ]
        if len(observed["targets"]) < 3:
            selected = self._batch_selector.select(pool, campaign.budget.batch_size)
            return selected, self._build_state(
                campaign,
                observed["targets"],
                previous_payload=state.payload if state else None,
                active_bounds=active_bounds,
                search_stage=stage_name,
            )

        model = GaussianProcessRegressor(
            kernel=Matern(nu=2.5) + WhiteKernel(noise_level=1e-5),
            normalize_y=True,
            random_state=self._random_seed,
        )
        model.fit(np.asarray(observed["features"]), np.asarray(observed["targets"]))
        scored: list[Candidate] = []
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
            campaign,
            observed["targets"],
            previous_payload=state.payload if state else None,
            active_bounds=active_bounds,
            search_stage=stage_name,
        )

    def _build_active_bounds(
        self,
        campaign: Campaign,
        previous_candidates: list[Candidate],
        previous_runs: list[SimulationRun],
        targets: list[float],
    ) -> dict[str, dict[str, float]] | None:
        if len(targets) < self._coarse_observation_count:
            return None
        candidate_map = {candidate.id: candidate for candidate in previous_candidates}
        ranked_candidates: list[tuple[Candidate, float]] = []
        for run in previous_runs:
            if not self._is_feasible_run(run):
                continue
            candidate = candidate_map.get(run.candidate_id)
            if candidate is None or not run.metrics:
                continue
            ranked_candidates.append(
                (candidate, compute_objective_score(campaign.objectives, run.metrics))
            )
        if not ranked_candidates:
            return None
        ranked_candidates.sort(key=lambda item: item[1], reverse=True)
        top_candidates = [candidate for candidate, _score in ranked_candidates[: self._top_candidate_count]]
        active_bounds: dict[str, dict[str, float]] = {}
        for dimension in campaign.search_space.dimensions:
            if dimension.kind == ParameterKind.CATEGORICAL:
                continue
            if dimension.lower is None or dimension.upper is None:
                continue
            values = [float(candidate.values[dimension.name]) for candidate in top_candidates]
            if not values:
                continue
            lower = float(dimension.lower)
            upper = float(dimension.upper)
            total_span = upper - lower
            candidate_low = min(values)
            candidate_high = max(values)
            local_span = max(candidate_high - candidate_low, total_span * 0.05)
            padding = max(total_span * self._padding_fraction, 0.5 * local_span)
            narrowed_low = max(lower, candidate_low - padding)
            narrowed_high = min(upper, candidate_high + padding)
            minimum_window = min(total_span, total_span * self._minimum_window_fraction)
            center = 0.5 * (candidate_low + candidate_high)
            narrowed_low, narrowed_high = self._normalize_bounds(
                original_lower=lower,
                original_upper=upper,
                proposed_lower=narrowed_low,
                proposed_upper=narrowed_high,
                center=center,
                minimum_window=minimum_window,
            )
            active_bounds[dimension.name] = {
                "lower": narrowed_low,
                "upper": narrowed_high,
            }
        return active_bounds

    def _normalize_bounds(
        self,
        *,
        original_lower: float,
        original_upper: float,
        proposed_lower: float,
        proposed_upper: float,
        center: float,
        minimum_window: float,
    ) -> tuple[float, float]:
        lower = max(original_lower, min(proposed_lower, proposed_upper))
        upper = min(original_upper, max(proposed_lower, proposed_upper))
        if upper - lower >= minimum_window or minimum_window <= 0:
            return lower, upper
        total_span = original_upper - original_lower
        if total_span <= minimum_window:
            return original_lower, original_upper
        clamped_center = min(max(center, original_lower + 0.5 * minimum_window), original_upper - 0.5 * minimum_window)
        normalized_lower = clamped_center - 0.5 * minimum_window
        normalized_upper = clamped_center + 0.5 * minimum_window
        return normalized_lower, normalized_upper

    def _sample_candidate_with_bounds(
        self,
        campaign: Campaign,
        rng: np.random.Generator,
        *,
        batch_index: int,
        active_bounds: dict[str, dict[str, float]] | None,
        stage_name: str,
    ) -> Candidate:
        values: dict[str, float | int | str] = {}
        for dimension in campaign.search_space.dimensions:
            values[dimension.name] = self._sample_dimension_with_bounds(
                dimension, rng, active_bounds.get(dimension.name) if active_bounds else None
            )
        return Candidate(
            id=uuid4(),
            campaign_id=campaign.id,
            values=values,
            batch_index=batch_index,
            source="coarse_to_fine_bayesian_optimizer",
            metadata={"seed": campaign.seed, "search_stage": stage_name},
        )

    def _sample_dimension_with_bounds(
        self,
        dimension: SearchSpaceDimension,
        rng: np.random.Generator,
        active_bounds: dict[str, float] | None,
    ) -> float | int | str:
        if dimension.kind == ParameterKind.CATEGORICAL:
            return str(rng.choice(dimension.choices))
        lower, upper = self._resolve_sampling_bounds(dimension, active_bounds)
        if dimension.kind == ParameterKind.INTEGER:
            lower = int(np.floor(lower))
            upper = int(np.ceil(upper))
            if upper < lower:
                original_lower = int(dimension.lower or 0)
                original_upper = int(dimension.upper or original_lower)
                lower = min(original_lower, original_upper)
                upper = max(original_lower, original_upper)
            if upper == lower:
                return lower
            return int(rng.integers(lower, upper + 1))
        if upper <= lower:
            return round(lower, 5)
        return round(float(rng.uniform(lower, upper)), 5)

    def _resolve_sampling_bounds(
        self,
        dimension: SearchSpaceDimension,
        active_bounds: dict[str, float] | None,
    ) -> tuple[float, float]:
        original_lower = float(dimension.lower or 0.0)
        original_upper = float(dimension.upper or original_lower)
        lower = min(original_lower, original_upper)
        upper = max(original_lower, original_upper)
        if not active_bounds:
            return lower, upper
        proposed_lower = float(active_bounds.get("lower", lower))
        proposed_upper = float(active_bounds.get("upper", upper))
        if not np.isfinite(proposed_lower) or not np.isfinite(proposed_upper):
            return lower, upper
        narrowed_lower = max(lower, min(proposed_lower, proposed_upper))
        narrowed_upper = min(upper, max(proposed_lower, proposed_upper))
        if not np.isfinite(narrowed_lower) or not np.isfinite(narrowed_upper):
            return lower, upper
        if narrowed_upper < narrowed_lower:
            return lower, upper
        return narrowed_lower, narrowed_upper

    def _build_state(
        self,
        campaign: Campaign,
        targets: list[float],
        previous_payload: dict[str, object] | None = None,
        *,
        active_bounds: dict[str, dict[str, float]] | None,
        search_stage: str,
    ) -> OptimizerState:
        state = super()._build_state(campaign, targets, previous_payload=previous_payload)
        state.algorithm = self.algorithm_name
        state.payload["search_stage"] = search_stage
        if active_bounds:
            state.payload["active_bounds"] = active_bounds
        state.payload["coarse_observation_count"] = self._coarse_observation_count
        state.payload["top_candidate_count"] = self._top_candidate_count
        return state
