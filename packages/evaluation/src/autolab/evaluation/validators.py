from __future__ import annotations

from uuid import UUID

from autolab.core.enums import ConstraintOperator
from autolab.core.models import Constraint, ValidationIssue, ValidationReport


def _passes_constraint(constraint: Constraint, metric_value: float) -> bool:
    if constraint.operator == ConstraintOperator.LESS_THAN:
        return metric_value < constraint.threshold
    if constraint.operator == ConstraintOperator.LESS_THAN_EQUAL:
        return metric_value <= constraint.threshold
    if constraint.operator == ConstraintOperator.GREATER_THAN:
        return metric_value > constraint.threshold
    return metric_value >= constraint.threshold


def validate_constraints(
    constraints: list[Constraint],
    metrics: dict[str, float],
    run_id: UUID | str | None = None,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    for constraint in constraints:
        value = metrics.get(constraint.metric_key)
        if value is None:
            issues.append(
                ValidationIssue(
                    code="missing_metric",
                    message=(
                        f"Metric '{constraint.metric_key}' missing "
                        f"for constraint '{constraint.name}'"
                    ),
                )
            )
            continue
        if not _passes_constraint(constraint, value):
            issues.append(
                ValidationIssue(
                    code="constraint_violation",
                    message=(
                        f"Constraint '{constraint.name}' failed with value {value} "
                        f"against threshold {constraint.threshold}"
                    ),
                )
            )
    return ValidationReport(run_id=run_id, valid=not issues, issues=issues, derived_metrics=metrics)
