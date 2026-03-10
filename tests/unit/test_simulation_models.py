from autolab.core.enums import CampaignMode, ObjectiveDirection, ParameterKind, SimulatorKind
from autolab.core.models import (
    Campaign,
    CampaignBudget,
    ExperimentSpec,
    Objective,
    SearchSpace,
    SearchSpaceDimension,
    SimulationStage,
    SimulationTask,
    SimulationWorkflow,
)
from pydantic import ValidationError


def test_workflow_model_orders_stages() -> None:
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
            ),
        ],
    )
    assert [stage.name for stage in workflow.ordered_stages()] == ["qe", "meep"]


def test_workflow_model_rejects_cycles() -> None:
    try:
        SimulationWorkflow(
            name="bad",
            stages=[
                SimulationStage(
                    name="a",
                    simulator=SimulatorKind.LAMMPS,
                    task=SimulationTask(name="a", simulator=SimulatorKind.LAMMPS),
                    depends_on=["b"],
                ),
                SimulationStage(
                    name="b",
                    simulator=SimulatorKind.MEEP,
                    task=SimulationTask(name="b", simulator=SimulatorKind.MEEP),
                    depends_on=["a"],
                ),
            ],
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("cyclic workflow should fail validation")


def test_campaign_accepts_optional_workflow() -> None:
    workflow = SimulationWorkflow(
        name="single",
        stages=[
            SimulationStage(
                name="primary",
                simulator=SimulatorKind.LAMMPS,
                task=SimulationTask(name="lammps_md", simulator=SimulatorKind.LAMMPS),
            )
        ],
    )
    campaign = Campaign(
        name="workflow-campaign",
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
                    upper=5.0,
                )
            ]
        ),
        budget=CampaignBudget(max_runs=2, batch_size=1, max_failures=1),
        simulator=SimulatorKind.LAMMPS,
        workflow=workflow,
    )
    assert campaign.workflow is not None


def test_experiment_spec_keeps_stage_context() -> None:
    spec = ExperimentSpec(
        campaign_id="00000000-0000-0000-0000-000000000001",
        candidate_id="00000000-0000-0000-0000-000000000002",
        simulator=SimulatorKind.MEEP,
        stage_name="optics",
        parameters={"resolution": 20},
    )
    assert spec.stage_name == "optics"
