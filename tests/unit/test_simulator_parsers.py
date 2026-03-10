from pathlib import Path

from autolab.core.enums import RunStatus, SimulatorKind
from autolab.core.models import SimulationExecutionRecord
from autolab.core.settings import get_settings
from autolab.simulators.devsim import DevsimSimulator
from autolab.simulators.elmer import ElmerSimulator
from autolab.simulators.lammps import LammpsSimulator
from autolab.simulators.meep import MeepSimulator
from autolab.simulators.openmm import OpenMMSimulator
from autolab.simulators.quantum_espresso import QuantumEspressoSimulator


def _execution(simulator: SimulatorKind, fixture_dir: str) -> SimulationExecutionRecord:
    return SimulationExecutionRecord(
        experiment_id="00000000-0000-0000-0000-000000000010",
        campaign_id="00000000-0000-0000-0000-000000000011",
        candidate_id="00000000-0000-0000-0000-000000000012",
        simulator=simulator,
        stage_name="primary",
        workdir_path=str(Path("tests/fixtures/simulators") / fixture_dir),
        status=RunStatus.SUCCEEDED,
    )


def test_lammps_parser_reads_fixture() -> None:
    parsed = LammpsSimulator(get_settings()).parse_outputs(
        _execution(SimulatorKind.LAMMPS, "lammps")
    )
    assert parsed.scalar_metrics["temperature"] == 0.95
    assert parsed.scalar_metrics["loop_time_seconds"] == 0.002
    assert parsed.metadata["completion_detected"] is True


def test_meep_parser_reads_fixture() -> None:
    parsed = MeepSimulator(get_settings()).parse_outputs(_execution(SimulatorKind.MEEP, "meep"))
    assert parsed.scalar_metrics["transmission_peak"] > 0.6


def test_qe_parser_reads_fixture() -> None:
    parsed = QuantumEspressoSimulator(get_settings()).parse_outputs(
        _execution(SimulatorKind.QUANTUM_ESPRESSO, "quantum_espresso")
    )
    assert parsed.scalar_metrics["total_energy_ry"] < 0


def test_openmm_parser_reads_fixture() -> None:
    parsed = OpenMMSimulator(get_settings()).parse_outputs(
        _execution(SimulatorKind.OPENMM, "openmm")
    )
    assert parsed.scalar_metrics["temperature"] == 300.0


def test_elmer_parser_reads_fixture() -> None:
    parsed = ElmerSimulator(get_settings()).parse_outputs(_execution(SimulatorKind.ELMER, "elmer"))
    assert "residual_norm" in parsed.scalar_metrics


def test_devsim_parser_reads_fixture() -> None:
    parsed = DevsimSimulator(get_settings()).parse_outputs(
        _execution(SimulatorKind.DEVSIM, "devsim")
    )
    assert parsed.scalar_metrics["drain_current"] > 0
