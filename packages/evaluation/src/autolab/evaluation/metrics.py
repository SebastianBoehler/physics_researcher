from __future__ import annotations

from autolab.core.enums import ObjectiveDirection
from autolab.core.models import Objective


def compute_objective_score(objectives: list[Objective], metrics: dict[str, float]) -> float:
    total = 0.0
    for objective in objectives:
        raw_value = metrics.get(objective.metric_key, 0.0)
        signed_value = (
            raw_value if objective.direction == ObjectiveDirection.MAXIMIZE else -raw_value
        )
        total += signed_value * objective.weight
    return total
