from __future__ import annotations

from autolab.core.enums import SimulatorKind
from autolab.core.settings import Settings
from autolab.simulators.base import SimulatorBackend
from autolab.simulators.devsim import DevsimSimulator
from autolab.simulators.elmer import ElmerSimulator
from autolab.simulators.lammps import LammpsSimulator
from autolab.simulators.meep import MeepSimulator
from autolab.simulators.openmm import OpenMMSimulator
from autolab.simulators.quantum_espresso import QuantumEspressoSimulator


class SimulatorRegistry:
    def __init__(self) -> None:
        self._registry: dict[SimulatorKind, SimulatorBackend] = {}

    def register(self, kind: SimulatorKind, backend: SimulatorBackend) -> None:
        self._registry[kind] = backend

    def get(self, kind: SimulatorKind) -> SimulatorBackend:
        return self._registry[kind]


def build_default_registry(settings: Settings) -> SimulatorRegistry:
    registry = SimulatorRegistry()
    registry.register(SimulatorKind.LAMMPS, LammpsSimulator(settings=settings))
    registry.register(SimulatorKind.MEEP, MeepSimulator(settings=settings))
    registry.register(SimulatorKind.QUANTUM_ESPRESSO, QuantumEspressoSimulator(settings=settings))
    registry.register(SimulatorKind.OPENMM, OpenMMSimulator(settings=settings))
    registry.register(SimulatorKind.ELMER, ElmerSimulator(settings=settings))
    registry.register(SimulatorKind.DEVSIM, DevsimSimulator(settings=settings))
    return registry
