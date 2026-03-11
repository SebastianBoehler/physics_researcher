from pathlib import Path

from autolab.core.models import Candidate
from autolab.core.settings import get_settings
from autolab.simulators.devsim import DevsimSimulator
from autolab.simulators.meep import MeepSimulator
from autolab.simulators.openmm import OpenMMSimulator


def test_script_backed_adapters_use_workdir_local_script_paths() -> None:
    candidate = Candidate(
        campaign_id="00000000-0000-0000-0000-000000000401",
        values={},
    )
    workdir = Path("artifacts/test-workdir")
    settings = get_settings()

    meep_spec = MeepSimulator(settings).create_experiment_spec(candidate)
    openmm_spec = OpenMMSimulator(settings).create_experiment_spec(candidate)
    devsim_spec = DevsimSimulator(settings).create_experiment_spec(candidate)

    assert MeepSimulator(settings).build_command(meep_spec, workdir)[1] == "launch.sh"
    assert OpenMMSimulator(settings).build_command(openmm_spec, workdir)[1] == "run_openmm.py"
    assert DevsimSimulator(settings).build_command(devsim_spec, workdir)[1] == "run_devsim.py"


def test_openmm_cluster_task_includes_reduced_coordinates() -> None:
    candidate = Candidate(
        campaign_id="00000000-0000-0000-0000-000000000402",
        values={
            "system_kind": "lj_cluster",
            "atom_count": "13",
            "atom_1_x": 1.05,
            "atom_2_x": 0.2,
            "atom_2_y": 1.1,
            "atom_3_x": -0.8,
            "atom_3_y": 0.4,
            "atom_3_z": 0.7,
        },
    )

    task = OpenMMSimulator(get_settings()).build_task(candidate)

    assert task.parameters["atom_count"] == 13
    assert len(task.parameters["cluster_positions"]) == 13
    assert task.parameters["cluster_positions"][0] == [0.0, 0.0, 0.0]
    assert task.parameters["cluster_positions"][1] == [1.05, 0.0, 0.0]
    assert task.parameters["cluster_positions"][2] == [0.2, 1.1, 0.0]
    assert task.parameters["cluster_positions"][3] == [-0.8, 0.4, 0.7]


def test_openmm_cluster_defaults_to_local_minimization() -> None:
    candidate = Candidate(
        campaign_id="00000000-0000-0000-0000-000000000403",
        values={
            "system_kind": "lj_cluster",
            "atom_count": "13",
        },
    )

    task = OpenMMSimulator(get_settings()).build_task(candidate)

    assert task.parameters["minimize_energy"] is True
    assert task.parameters["minimization_max_iterations"] == 10000
    assert task.parameters["minimization_tolerance"] == 1e-06
