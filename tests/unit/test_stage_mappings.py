from autolab.campaigns.stage_mapping import build_stage_mapping_registry
from autolab.core.enums import RunStatus, SimulatorKind
from autolab.core.models import (
    ExperimentSpec,
    SimulationParseResult,
    SimulationStage,
    SimulationTask,
)


def test_stage_mapping_registry_contains_expected_mappings() -> None:
    registry = build_stage_mapping_registry()
    assert registry.get("quantum_espresso_to_lammps") is not None
    assert registry.get("devsim_to_meep") is not None


def test_qe_to_meep_mapping_returns_refractive_index() -> None:
    registry = build_stage_mapping_registry()
    mapper = registry.get("quantum_espresso_to_meep")
    assert mapper is not None
    spec = ExperimentSpec(
        campaign_id="00000000-0000-0000-0000-000000000001",
        candidate_id="00000000-0000-0000-0000-000000000002",
        simulator=SimulatorKind.MEEP,
        stage_name="meep",
        parameters={},
    )
    parsed = SimulationParseResult(
        experiment_id="00000000-0000-0000-0000-000000000003",
        campaign_id="00000000-0000-0000-0000-000000000001",
        candidate_id="00000000-0000-0000-0000-000000000002",
        simulator=SimulatorKind.QUANTUM_ESPRESSO,
        stage_name="qe",
        status=RunStatus.SUCCEEDED,
        scalar_metrics={"total_energy_ry": -120.0},
    )
    next_stage = SimulationStage(
        name="meep",
        simulator=SimulatorKind.MEEP,
        task=SimulationTask(name="meep_flux", simulator=SimulatorKind.MEEP),
        depends_on=["qe"],
    )
    mapped = mapper(spec, parsed, next_stage)
    assert "refractive_index" in mapped
