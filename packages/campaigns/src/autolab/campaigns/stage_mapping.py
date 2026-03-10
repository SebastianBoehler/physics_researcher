from __future__ import annotations

from typing import Any

from autolab.core.models import ExperimentSpec, SimulationParseResult, SimulationStage
from autolab.simulators.core import StageMappingRegistry


def _qe_to_lammps(
    spec: ExperimentSpec, parsed: SimulationParseResult, _: SimulationStage
) -> dict[str, Any]:
    energy = abs(parsed.scalar_metrics.get("total_energy_ry", 30.0))
    return {
        "temperature": max(0.5, min(5.0, energy / 50.0)),
        "upstream_total_energy_ry": parsed.scalar_metrics.get("total_energy_ry"),
    }


def _qe_to_meep(
    spec: ExperimentSpec, parsed: SimulationParseResult, _: SimulationStage
) -> dict[str, Any]:
    energy = abs(parsed.scalar_metrics.get("total_energy_ry", 20.0))
    return {
        "refractive_index": max(1.2, min(4.0, 1.0 + energy / 40.0)),
        "upstream_total_energy_ry": parsed.scalar_metrics.get("total_energy_ry"),
    }


def _lammps_to_elmer(
    spec: ExperimentSpec, parsed: SimulationParseResult, _: SimulationStage
) -> dict[str, Any]:
    return {
        "heat_conductivity": max(1.0, abs(parsed.scalar_metrics.get("potential_energy", 10.0))),
        "upstream_temperature": parsed.scalar_metrics.get("temperature"),
    }


def _devsim_to_meep(
    spec: ExperimentSpec, parsed: SimulationParseResult, _: SimulationStage
) -> dict[str, Any]:
    current = abs(parsed.scalar_metrics.get("drain_current", 0.1))
    return {
        "fcen": max(0.05, min(0.3, 0.1 + current * 0.01)),
        "upstream_drain_current": parsed.scalar_metrics.get("drain_current"),
    }


def build_stage_mapping_registry() -> StageMappingRegistry:
    registry = StageMappingRegistry()
    registry.register("quantum_espresso_to_lammps", _qe_to_lammps)
    registry.register("quantum_espresso_to_meep", _qe_to_meep)
    registry.register("lammps_to_elmer", _lammps_to_elmer)
    registry.register("devsim_to_meep", _devsim_to_meep)
    return registry
