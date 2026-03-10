from autolab.core.enums import CampaignMode, ObjectiveDirection, ParameterKind, SimulatorKind
from autolab.core.models import (
    Campaign,
    CampaignBudget,
    Candidate,
    Objective,
    SearchSpace,
    SearchSpaceDimension,
)
from autolab.core.settings import get_settings
from autolab.simulators import FakeSimulator, LammpsSimulator, OpenMMSimulator, SimulatorBackend


def _candidate() -> Candidate:
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
                )
            ]
        ),
        budget=CampaignBudget(max_runs=2, batch_size=1, max_failures=1),
        simulator=SimulatorKind.FAKE,
    )
    return Candidate(
        campaign_id=campaign.id,
        values={
            "dopant_ratio": 0.3,
            "anneal_temperature": 600.0,
            "pressure": 2.0,
            "synthesis_time": 2.0,
        },
    )


def test_adapters_implement_contract() -> None:
    settings = get_settings()
    adapters: list[SimulatorBackend] = [
        FakeSimulator(settings),
        LammpsSimulator(settings),
        OpenMMSimulator(settings),
    ]
    for adapter in adapters:
        prepared = adapter.prepare_input(_candidate())
        handle = adapter.run(prepared)
        status = adapter.poll(handle)
        result = adapter.parse(handle)
        validation = adapter.validate(result)
        assert prepared.simulator.value == handle.simulator.value
        assert status.job_id == handle.id
        assert validation.report.run_id == result.run_id
