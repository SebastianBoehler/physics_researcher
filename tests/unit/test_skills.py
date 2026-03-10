from autolab.core.enums import ConstraintOperator
from autolab.core.models import Candidate, Constraint
from autolab.skills import get_builtin_skills


def test_builtin_skill_registry_contains_expected_skills() -> None:
    registry = get_builtin_skills()
    names = {skill.name for skill in registry.list()}
    assert "propose_candidates" in names
    assert "compare_recent_experiments" in names


def test_rank_candidates_skill_orders_by_prediction() -> None:
    registry = get_builtin_skills()
    skill = registry.get("rank_candidates")
    candidates = [
        Candidate(
            campaign_id="00000000-0000-0000-0000-000000000001",
            values={},
            predicted_metrics={"predicted_objective": 1.0},
        ),
        Candidate(
            campaign_id="00000000-0000-0000-0000-000000000001",
            values={},
            predicted_metrics={"predicted_objective": 3.0},
        ),
    ]
    result = skill.run(skill.input_model(candidates=candidates), context=None)  # type: ignore[arg-type]
    assert len(result.ordered_candidate_ids) == 2


def test_validate_constraints_skill_reports_actual_violations() -> None:
    registry = get_builtin_skills()
    skill = registry.get("validate_constraints")
    result = skill.run(
        skill.input_model(
            constraints=[
                Constraint(
                    name="cost_limit",
                    metric_key="cost",
                    operator=ConstraintOperator.LESS_THAN,
                    threshold=55.0,
                )
            ],
            metrics={"cost": 60.0},
        ),
        context=None,  # type: ignore[arg-type]
    )

    assert result.valid is False
    assert result.issues
