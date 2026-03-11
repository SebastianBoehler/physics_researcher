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
from autolab.optimizers import (
    BayesianOptimizer,
    CoarseToFineBayesianOptimizer,
    RandomSearchOptimizer,
    build_optimizer,
)
import numpy as np


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


def test_random_search_optimizer_samples_within_bounds() -> None:
    campaign = _campaign()
    optimizer = RandomSearchOptimizer(random_seed=11)

    batch, state = optimizer.suggest(
        campaign,
        previous_candidates=[],
        previous_runs=[],
        state=None,
    )

    assert len(batch) == campaign.budget.batch_size
    for candidate in batch:
        value = float(candidate.values["dopant_ratio"])
        assert 0.1 <= value <= 0.5
        assert candidate.source == "random_search_optimizer"
    assert state.algorithm == "random_search"


def test_build_optimizer_from_metadata() -> None:
    optimizer = build_optimizer({"optimizer": {"algorithm": "random_search", "random_seed": 9}})
    assert isinstance(optimizer, RandomSearchOptimizer)


def test_build_coarse_to_fine_optimizer_from_metadata() -> None:
    optimizer = build_optimizer(
        {
            "optimizer": {
                "algorithm": "coarse_to_fine_bayesian",
                "coarse_observation_count": 4,
            }
        }
    )
    assert isinstance(optimizer, CoarseToFineBayesianOptimizer)


def test_coarse_to_fine_optimizer_shrinks_search_bounds_after_coarse_stage() -> None:
    campaign = _campaign()
    optimizer = CoarseToFineBayesianOptimizer(
        random_seed=5,
        candidate_pool_size=6,
        coarse_observation_count=4,
        top_candidate_count=2,
        minimum_window_fraction=0.1,
        padding_fraction=0.05,
    )
    candidates = [
        Candidate(campaign_id=campaign.id, values={"dopant_ratio": 0.18}),
        Candidate(campaign_id=campaign.id, values={"dopant_ratio": 0.22}),
        Candidate(campaign_id=campaign.id, values={"dopant_ratio": 0.24}),
        Candidate(campaign_id=campaign.id, values={"dopant_ratio": 0.41}),
    ]
    runs = [
        SimulationRun(
            campaign_id=campaign.id,
            candidate_id=candidates[0].id,
            simulator=SimulatorKind.LAMMPS,
            metrics={"conductivity": 20.0},
            metadata={"validation": {"valid": True}},
        ),
        SimulationRun(
            campaign_id=campaign.id,
            candidate_id=candidates[1].id,
            simulator=SimulatorKind.LAMMPS,
            metrics={"conductivity": 22.0},
            metadata={"validation": {"valid": True}},
        ),
        SimulationRun(
            campaign_id=campaign.id,
            candidate_id=candidates[2].id,
            simulator=SimulatorKind.LAMMPS,
            metrics={"conductivity": 21.5},
            metadata={"validation": {"valid": True}},
        ),
        SimulationRun(
            campaign_id=campaign.id,
            candidate_id=candidates[3].id,
            simulator=SimulatorKind.LAMMPS,
            metrics={"conductivity": 5.0},
            metadata={"validation": {"valid": True}},
        ),
    ]

    batch, state = optimizer.suggest(
        campaign,
        previous_candidates=candidates,
        previous_runs=runs,
        state=None,
    )

    bounds = state.payload["active_bounds"]["dopant_ratio"]
    assert state.algorithm == "coarse_to_fine_bayesian"
    assert state.payload["search_stage"] == "refine"
    assert bounds["lower"] < 0.22 < bounds["upper"]
    assert bounds["upper"] < 0.5
    for candidate in batch:
        value = float(candidate.values["dopant_ratio"])
        assert bounds["lower"] <= value <= bounds["upper"]
        assert candidate.metadata["search_stage"] == "refine"


def test_coarse_to_fine_optimizer_handles_edge_contraction() -> None:
    campaign = _campaign()
    optimizer = CoarseToFineBayesianOptimizer(
        random_seed=3,
        candidate_pool_size=4,
        coarse_observation_count=3,
        top_candidate_count=2,
        minimum_window_fraction=0.3,
        padding_fraction=0.01,
    )
    candidates = [
        Candidate(campaign_id=campaign.id, values={"dopant_ratio": 0.47}),
        Candidate(campaign_id=campaign.id, values={"dopant_ratio": 0.49}),
        Candidate(campaign_id=campaign.id, values={"dopant_ratio": 0.12}),
    ]
    runs = [
        SimulationRun(
            campaign_id=campaign.id,
            candidate_id=candidates[0].id,
            simulator=SimulatorKind.LAMMPS,
            metrics={"conductivity": 47.0},
            metadata={"validation": {"valid": True}},
        ),
        SimulationRun(
            campaign_id=campaign.id,
            candidate_id=candidates[1].id,
            simulator=SimulatorKind.LAMMPS,
            metrics={"conductivity": 49.0},
            metadata={"validation": {"valid": True}},
        ),
        SimulationRun(
            campaign_id=campaign.id,
            candidate_id=candidates[2].id,
            simulator=SimulatorKind.LAMMPS,
            metrics={"conductivity": 12.0},
            metadata={"validation": {"valid": True}},
        ),
    ]

    batch, state = optimizer.suggest(
        campaign,
        previous_candidates=candidates,
        previous_runs=runs,
        state=None,
    )

    bounds = state.payload["active_bounds"]["dopant_ratio"]
    assert bounds["lower"] < bounds["upper"]
    for candidate in batch:
        value = float(candidate.values["dopant_ratio"])
        assert bounds["lower"] <= value <= bounds["upper"]


def test_coarse_to_fine_optimizer_falls_back_from_inverted_active_bounds() -> None:
    campaign = _campaign()
    optimizer = CoarseToFineBayesianOptimizer(random_seed=13, candidate_pool_size=4)

    samples = [
        float(
            optimizer._sample_dimension_with_bounds(  # noqa: SLF001 - direct edge-case coverage
                campaign.search_space.dimensions[0],
                np.random.default_rng(17 + index),
                {"lower": 0.41, "upper": 0.19},
            )
        )
        for index in range(4)
    ]

    for value in samples:
        assert 0.1 <= value <= 0.5
