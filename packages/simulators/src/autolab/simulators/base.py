from __future__ import annotations

from typing import Protocol

from autolab.core.models import Candidate, SimulationResult
from autolab.simulators.types import JobHandle, PreparedRun, SimulationStatus, ValidationOutcome


class SimulatorBackend(Protocol):
    simulator_name: str

    def prepare_input(self, candidate: Candidate) -> PreparedRun: ...

    def run(self, prepared_run: PreparedRun) -> JobHandle: ...

    def poll(self, job_handle: JobHandle) -> SimulationStatus: ...

    def parse(self, job_handle: JobHandle) -> SimulationResult: ...

    def validate(self, result: SimulationResult) -> ValidationOutcome: ...
