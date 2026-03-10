from autolab.core.enums import CampaignMode, ObjectiveDirection, ParameterKind, SimulatorKind
from autolab.core.models import (
    Campaign,
    CampaignBudget,
    Candidate,
    Objective,
    SearchSpace,
    SearchSpaceDimension,
    SimulationRun,
)
from autolab.optimizers import BayesianOptimizer


def _campaign() -> Campaign:
    return Campaign(
        name="optimizer-demo",
        mode=CampaignMode.MATERIALS_DISCOVERY,
        objectives=[
            Objective(
                name="maximize_conductivity",
                metric_key="conductivity",
                direction=ObjectiveDirection.MAXIMIZE,
            )
        ],
        search_space=SearchSpace(
            dimensions=[
                SearchSpaceDimension(
                    name="dopant_ratio",
                    kind=ParameterKind.CONTINUOUS,
                    lower=0.1,
                    upper=0.5,
                )
            ]
        ),
        budget=CampaignBudget(max_runs=6, batch_size=2, max_failures=2),
        simulator=SimulatorKind.LAMMPS,
    )


def test_bayesian_optimizer_ignores_infeasible_observations() -> None:
    campaign = _campaign()
    optimizer = BayesianOptimizer(random_seed=7, candidate_pool_size=4)
    feasible_candidate = Candidate(campaign_id=campaign.id, values={"dopant_ratio": 0.2})
    infeasible_candidate = Candidate(campaign_id=campaign.id, values={"dopant_ratio": 0.4})
    previous_runs = [
        SimulationRun(
            campaign_id=campaign.id,
            candidate_id=infeasible_candidate.id,
            simulator=SimulatorKind.LAMMPS,
            metrics={"conductivity": 100.0},
            metadata={
                "objective_score": 100.0,
                "validation": {"valid": False},
            },
        ),
        SimulationRun(
            campaign_id=campaign.id,
            candidate_id=feasible_candidate.id,
            simulator=SimulatorKind.LAMMPS,
            metrics={"conductivity": 20.0},
            metadata={
                "objective_score": 20.0,
                "validation": {"valid": True},
            },
        ),
    ]

    _, state = optimizer.suggest(
        campaign,
        previous_candidates=[feasible_candidate, infeasible_candidate],
        previous_runs=previous_runs,
        state=None,
    )

    assert state.observation_count == 1
    assert state.payload["best_observed_objective"] == 20.0
    assert state.payload["feasible_observation_count"] == 1
