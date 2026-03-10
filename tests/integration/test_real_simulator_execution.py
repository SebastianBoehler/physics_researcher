from __future__ import annotations

import importlib.util
import shutil

import pytest
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
from autolab.simulators.lammps import LammpsSimulator
from autolab.simulators.meep import MeepSimulator
from autolab.simulators.openmm import OpenMMSimulator


def _candidate(simulator: SimulatorKind) -> Candidate:
    campaign = Campaign(
        name="integration",
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
        budget=CampaignBudget(max_runs=1, batch_size=1, max_failures=1),
        simulator=simulator,
    )
    values: dict[str, float | int | str] = {"temperature": 1.0}
    if simulator == SimulatorKind.LAMMPS:
        values.update(
            {
                "steps": 25,
                "thermo_frequency": 5,
                "timestep": 0.002,
                "ensemble": "nve",
            }
        )
    return Candidate(campaign_id=campaign.id, values=values)


def test_lammps_real_execution_if_available() -> None:
    settings = get_settings()
    if shutil.which(settings.simulators.lammps_bin) is None:
        pytest.skip("LAMMPS binary not installed")
    simulator = LammpsSimulator(settings)
    prepared = simulator.prepare_input(_candidate(SimulatorKind.LAMMPS))
    handle = simulator.run(prepared)
    result = simulator.parse(handle)
    assert result.status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.TIMED_OUT}


def test_meep_real_execution_if_available() -> None:
    if importlib.util.find_spec("meep") is None:
        pytest.skip("meep Python module not installed")
    simulator = MeepSimulator(get_settings())
    prepared = simulator.prepare_input(_candidate(SimulatorKind.MEEP))
    handle = simulator.run(prepared)
    result = simulator.parse(handle)
    assert result.status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.TIMED_OUT}


def test_openmm_real_execution_if_available() -> None:
    if importlib.util.find_spec("openmm") is None:
        pytest.skip("openmm Python module not installed")
    settings = get_settings()
    simulator = OpenMMSimulator(settings)
    candidate = _candidate(SimulatorKind.OPENMM)
    candidate.values.update(
        {
            "system_kind": "lj_pair",
            "platform_name": "CPU",
            "initial_distance": 0.39,
            "temperature": 1.0,
            "steps": 0,
            "friction": 1.0,
            "step_size_fs": 1.0,
        }
    )
    prepared = simulator.prepare_input(candidate)
    handle = simulator.run(prepared)
    result = simulator.parse(handle)
    assert result.status == RunStatus.SUCCEEDED
