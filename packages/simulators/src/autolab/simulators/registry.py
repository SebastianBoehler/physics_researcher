from __future__ import annotations

from autolab.core.enums import SimulatorKind
from autolab.core.settings import Settings
from autolab.simulators.base import SimulatorBackend
from autolab.simulators.fake import FakeSimulator
from autolab.simulators.lammps import LammpsSimulator
from autolab.simulators.openmm import OpenMMSimulator


class SimulatorRegistry:
    def __init__(self) -> None:
        self._registry: dict[SimulatorKind, SimulatorBackend] = {}

    def register(self, kind: SimulatorKind, backend: SimulatorBackend) -> None:
        self._registry[kind] = backend

    def get(self, kind: SimulatorKind) -> SimulatorBackend:
        return self._registry[kind]


def build_default_registry(settings: Settings) -> SimulatorRegistry:
    registry = SimulatorRegistry()
    registry.register(SimulatorKind.FAKE, FakeSimulator(settings=settings))
    registry.register(SimulatorKind.LAMMPS, LammpsSimulator(settings=settings))
    registry.register(SimulatorKind.OPENMM, OpenMMSimulator(settings=settings))
    return registry
