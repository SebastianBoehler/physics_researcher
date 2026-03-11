from __future__ import annotations

from typing import Any

from autolab.optimizers.base import BatchSelector, Optimizer, RLPolicy
from autolab.optimizers.bayesian import BayesianOptimizer
from autolab.optimizers.coarse_to_fine import CoarseToFineBayesianOptimizer
from autolab.optimizers.random_search import RandomSearchOptimizer


def build_optimizer(metadata: dict[str, Any] | None = None) -> Optimizer:
    metadata = metadata or {}
    raw_config = metadata.get("optimizer", {})
    optimizer_config = raw_config if isinstance(raw_config, dict) else {}
    algorithm = str(
        optimizer_config.get("algorithm", metadata.get("optimizer_algorithm", "bayesian_gp"))
    ).strip()
    if algorithm in {"bayesian", "bayesian_gp", "default"}:
        return BayesianOptimizer(
            random_seed=int(optimizer_config.get("random_seed", 42)),
            candidate_pool_size=int(optimizer_config.get("candidate_pool_size", 32)),
        )
    if algorithm in {"coarse_to_fine_bayesian", "coarse_to_fine_gp", "bayesian_coarse_to_fine"}:
        return CoarseToFineBayesianOptimizer(
            random_seed=int(optimizer_config.get("random_seed", 42)),
            candidate_pool_size=int(optimizer_config.get("candidate_pool_size", 48)),
            coarse_observation_count=int(optimizer_config.get("coarse_observation_count", 6)),
            top_candidate_count=int(optimizer_config.get("top_candidate_count", 3)),
            minimum_window_fraction=float(optimizer_config.get("minimum_window_fraction", 0.2)),
            padding_fraction=float(optimizer_config.get("padding_fraction", 0.08)),
        )
    if algorithm in {"random", "random_search"}:
        return RandomSearchOptimizer(random_seed=int(optimizer_config.get("random_seed", 42)))
    msg = f"unsupported optimizer algorithm: {algorithm}"
    raise ValueError(msg)


__all__ = [
    "BatchSelector",
    "BayesianOptimizer",
    "CoarseToFineBayesianOptimizer",
    "Optimizer",
    "RLPolicy",
    "RandomSearchOptimizer",
    "build_optimizer",
]
