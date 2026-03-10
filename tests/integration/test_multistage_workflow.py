from autolab.campaigns.workflow_graph import resolve_campaign_workflow, stage_order
from autolab.core.enums import (
    CampaignMode,
    ObjectiveDirection,
    ParameterKind,
    SimulatorKind,
)
from autolab.core.models import (
    Campaign,
    CampaignBudget,
    Candidate,
    Objective,
    SearchSpace,
    SearchSpaceDimension,
    SimulationStage,
    SimulationTask,
    SimulationWorkflow,
)
from autolab.core.settings import get_settings
from autolab.simulators.registry import build_default_registry


def test_resolve_campaign_workflow_uses_configured_workflow() -> None:
    workflow = SimulationWorkflow(
        name="qe-to-meep",
        stages=[
            SimulationStage(
                name="qe",
                simulator=SimulatorKind.QUANTUM_ESPRESSO,
                task=SimulationTask(name="qe", simulator=SimulatorKind.QUANTUM_ESPRESSO),
            ),
            SimulationStage(
                name="meep",
                simulator=SimulatorKind.MEEP,
                task=SimulationTask(name="meep", simulator=SimulatorKind.MEEP),
                depends_on=["qe"],
                mapping_id="quantum_espresso_to_meep",
            ),
        ],
    )
    campaign = Campaign(
        name="multi",
        mode=CampaignMode.MATERIALS_DISCOVERY,
        objectives=[
            Objective(
                name="obj",
                metric_key="transmission_peak",
                direction=ObjectiveDirection.MAXIMIZE,
            )
        ],
        search_space=SearchSpace(
            dimensions=[
                SearchSpaceDimension(
                    name="ecutwfc",
                    kind=ParameterKind.CONTINUOUS,
                    lower=20.0,
                    upper=80.0,
                )
            ]
        ),
        budget=CampaignBudget(max_runs=1, batch_size=1, max_failures=1),
        simulator=SimulatorKind.QUANTUM_ESPRESSO,
        workflow=workflow,
    )
    candidate = Candidate(campaign_id=campaign.id, values={"ecutwfc": 30.0})
    resolved = resolve_campaign_workflow(
        campaign, candidate, build_default_registry(get_settings())
    )
    assert [stage.name for stage in stage_order(resolved)] == ["qe", "meep"]


def test_default_workflow_falls_back_to_backend_shape() -> None:
    campaign = Campaign(
        name="single",
        mode=CampaignMode.MATERIALS_DISCOVERY,
        objectives=[
            Objective(name="obj", metric_key="temperature", direction=ObjectiveDirection.MAXIMIZE)
        ],
        search_space=SearchSpace(
            dimensions=[
                SearchSpaceDimension(
                    name="temperature",
                    kind=ParameterKind.CONTINUOUS,
                    lower=0.5,
                    upper=3.0,
                )
            ]
        ),
        budget=CampaignBudget(max_runs=1, batch_size=1, max_failures=1),
        simulator=SimulatorKind.LAMMPS,
    )
    candidate = Candidate(campaign_id=campaign.id, values={"temperature": 1.0})
    resolved = resolve_campaign_workflow(
        campaign, candidate, build_default_registry(get_settings())
    )
    assert resolved.stages[0].simulator == SimulatorKind.LAMMPS
