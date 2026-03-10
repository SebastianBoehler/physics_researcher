from autolab.core.enums import CampaignMode, ObjectiveDirection, ParameterKind, SimulatorKind
from autolab.core.models import (
    Campaign,
    CampaignBudget,
    Objective,
    SearchSpace,
    SearchSpaceDimension,
)


def test_campaign_model_builds() -> None:
    campaign = Campaign(
        name="demo",
        mode=CampaignMode.MATERIALS_DISCOVERY,
        objectives=[
            Objective(name="obj", metric_key="conductivity", direction=ObjectiveDirection.MAXIMIZE)
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
        budget=CampaignBudget(max_runs=4, batch_size=2, max_failures=1),
        simulator=SimulatorKind.LAMMPS,
    )
    assert campaign.budget.batch_size == 2
    assert campaign.objectives[0].metric_key == "conductivity"
