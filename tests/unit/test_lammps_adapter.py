from pathlib import Path

from autolab.core.enums import RunStatus, SimulatorKind
from autolab.core.models import Candidate, SimulationExecutionRecord
from autolab.core.settings import get_settings
from autolab.simulators.lammps import LammpsSimulator


def test_lammps_generate_inputs_supports_data_file_and_nvt(tmp_path: Path) -> None:
    data_file = tmp_path / "seed.data"
    data_file_contents = (
        "LAMMPS data file\n\n"
        "1 atoms\n"
        "1 atom types\n\n"
        "0 1 xlo xhi\n"
        "0 1 ylo yhi\n"
        "0 1 zlo zhi\n\n"
        "Masses\n\n"
        "1 1.0\n\n"
        "Atoms\n\n"
        "1 1 0.0 0.0 0.0\n"
    )
    data_file.write_text(
        data_file_contents,
        encoding="utf-8",
    )
    candidate = Candidate(
        campaign_id="00000000-0000-0000-0000-000000000101",
        values={
            "ensemble": "nvt",
            "start_temperature": 0.8,
            "target_temperature": 1.1,
            "thermostat_damping": 2.5,
            "thermo_frequency": 25,
            "timestep": 0.002,
            "dump_frequency": 50,
            "create_velocity": False,
        },
        metadata={"lammps_data_file": str(data_file)},
    )

    simulator = LammpsSimulator(get_settings())
    spec = simulator.create_experiment_spec(candidate)
    artifacts = simulator.generate_inputs(spec, tmp_path / "workdir")

    input_deck = (tmp_path / "workdir" / "in.lammps").read_text(encoding="utf-8")
    assert "read_data seed.data" in input_deck
    assert "fix integrator all nvt temp 0.8 1.1 2.5" in input_deck
    assert "thermo 25" in input_deck
    assert "timestep 0.002" in input_deck
    assert "dump atom_dump all custom 50 trajectory.lammpstrj id type x y z" in input_deck
    assert "velocity all create" not in input_deck
    assert (tmp_path / "workdir" / "seed.data").exists()
    assert any(artifact.artifact_role == "input_data_file" for artifact in artifacts)


def test_lammps_parser_handles_multisection_logs() -> None:
    execution = SimulationExecutionRecord(
        experiment_id="00000000-0000-0000-0000-000000000201",
        campaign_id="00000000-0000-0000-0000-000000000202",
        candidate_id="00000000-0000-0000-0000-000000000203",
        simulator=SimulatorKind.LAMMPS,
        stage_name="primary",
        workdir_path=str(Path("tests/fixtures/simulators/lammps_multisection")),
        status=RunStatus.SUCCEEDED,
    )
    parsed = LammpsSimulator(get_settings()).parse_outputs(execution)

    assert parsed.scalar_metrics["temperature"] == 0.94
    assert parsed.scalar_metrics["loop_time_seconds"] == 0.004
    assert parsed.scalar_metrics["atom_count"] == 64.0
    assert parsed.metadata["thermo_sections"] == 2
    assert parsed.metadata["thermo_rows"] == 4
    assert parsed.convergence is True
    assert "Neighbor list overflow" in " ".join(parsed.warnings)
    assert len(parsed.timeseries["temp"]) == 4


def test_lammps_validation_requires_log_file(tmp_path: Path) -> None:
    workdir = tmp_path / "workdir"
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "stdout.log").write_text(
        "Step Temp Press Pe Ke Etotal Vol Density\n0 1.0 0.0 -1.0 0.5 -0.5 64.0 0.95\n",
        encoding="utf-8",
    )
    execution = SimulationExecutionRecord(
        experiment_id="00000000-0000-0000-0000-000000000301",
        campaign_id="00000000-0000-0000-0000-000000000302",
        candidate_id="00000000-0000-0000-0000-000000000303",
        simulator=SimulatorKind.LAMMPS,
        stage_name="primary",
        workdir_path=str(workdir),
        status=RunStatus.SUCCEEDED,
    )
    simulator = LammpsSimulator(get_settings())
    parsed = simulator.parse_outputs(execution)
    validation = simulator.validate_parsed(parsed)

    assert validation.status == "invalid"
    assert "missing log.lammps output" in validation.reasons
