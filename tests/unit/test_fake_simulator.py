from autolab.core.enums import (
    CampaignMode,
    ObjectiveDirection,
    ParameterKind,
    RunStatus,
    SimulatorKind,
)
from autolab.core.models import (
    Campaign,
    CampaignBudget,
    Candidate,
    Objective,
    SearchSpace,
    SearchSpaceDimension,
)
from autolab.core.settings import get_settings
from autolab.simulators.fake import FakeSimulator


def test_fake_simulator_produces_metrics() -> None:
    settings = get_settings()
    simulator = FakeSimulator(settings)
    campaign = Campaign(
        name="demo",
        mode=CampaignMode.MATERIALS_DISCOVERY,
        objectives=[
            Objective(name="obj", metric_key="conductivity", direction=ObjectiveDirection.MAXIMIZE)
        ],
        search_space=SearchSpace(
            dimensions=[
                SearchSpaceDimension(
                    name="dopant_ratio", kind=ParameterKind.CONTINUOUS, lower=0.1, upper=0.5
                ),
                SearchSpaceDimension(
                    name="anneal_temperature",
                    kind=ParameterKind.CONTINUOUS,
                    lower=450.0,
                    upper=750.0,
                ),
                SearchSpaceDimension(
                    name="pressure", kind=ParameterKind.CONTINUOUS, lower=0.5, upper=3.5
                ),
                SearchSpaceDimension(
                    name="synthesis_time", kind=ParameterKind.CONTINUOUS, lower=1.0, upper=5.0
                ),
            ]
        ),
        budget=CampaignBudget(max_runs=4, batch_size=2, max_failures=1),
        simulator=SimulatorKind.FAKE,
    )
    candidate = Candidate(
        campaign_id=campaign.id,
        values={
            "dopant_ratio": 0.32,
            "anneal_temperature": 620.0,
            "pressure": 2.0,
            "synthesis_time": 3.0,
        },
    )
    prepared = simulator.prepare_input(candidate)
    handle = simulator.run(prepared)
    status = simulator.poll(handle)
    result = simulator.parse(handle)
    assert status.terminal is True
    assert result.status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.TIMED_OUT}
    assert "conductivity" in result.metrics
