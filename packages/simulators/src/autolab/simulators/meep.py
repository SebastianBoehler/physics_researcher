from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

from autolab.core.enums import ArtifactType, FailureClass, SimulatorKind
from autolab.core.models import (
    Candidate,
    ExperimentSpec,
    GeometrySpec,
    SimulationArtifact,
    SimulationExecutionRecord,
    SimulationParseResult,
    SimulationTask,
    SimulationValidationResult,
)
from autolab.core.settings import Settings
from autolab.simulators.core.adapter import WorkflowBackedSimulator
from autolab.simulators.core.artifacts import write_text_artifact
from jinja2 import Template


def _float_value(values: dict[str, Any], key: str, default: float) -> float:
    return float(values.get(key, default))


def _int_value(values: dict[str, Any], key: str, default: int) -> int:
    return int(values.get(key, default))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _power_db(value: float, *, floor: float = 1.0e-12) -> float:
    return 10.0 * math.log10(max(value, floor))


def _insertion_loss_db(value: float) -> float:
    return -_power_db(value)


def _return_loss_db(value: float) -> float:
    return -_power_db(value)


def _imbalance_db(first: float, second: float, *, floor: float = 1.0e-12) -> float:
    numerator = max(first, second, floor)
    denominator = max(min(first, second), floor)
    return 10.0 * math.log10(numerator / denominator)


def _bandwidth_fraction(values: list[float], predicate: Any) -> float:
    if not values:
        return 0.0
    hits = sum(1 for value in values if predicate(value))
    return hits / len(values)


def _split_halves(values: list[float]) -> tuple[list[float], list[float]]:
    if not values:
        return [], []
    midpoint = max(1, len(values) // 2)
    return values[:midpoint], values[midpoint:]


class MeepSimulator(WorkflowBackedSimulator):
    simulator_name = "meep"
    simulator_kind = SimulatorKind.MEEP

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._template_path = (
            Path(__file__).resolve().parent / "templates" / "meep" / "run_meep.py.j2"
        )

    @property
    def binary_name(self) -> str:
        configured = self._settings.simulators.meep_bin
        return sys.executable if configured == "python" else configured

    @property
    def enabled(self) -> bool:
        return self._settings.simulators.enable_meep

    @property
    def timeout_seconds(self) -> int:
        return self._settings.simulators.meep_timeout_seconds

    @property
    def command_wrapper(self) -> str | None:
        return self._settings.simulators.meep_wrapper

    @property
    def environment_overrides(self) -> dict[str, str]:
        return self._settings.simulators.meep_environment

    def build_task(self, candidate: Candidate) -> SimulationTask:
        values = candidate.values
        device_kind = str(values.get("device_kind", "waveguide_block"))
        geometry = GeometrySpec(
            kind=device_kind,
            parameters={
                "sx": _float_value(values, "sx", 16.0),
                "sy": _float_value(values, "sy", 8.0),
                "block_x": _float_value(values, "block_x", 1.0),
                "block_y": _float_value(values, "block_y", 4.0),
                "block_center_x": _float_value(values, "block_center_x", 0.0),
                "block_center_y": _float_value(values, "block_center_y", 0.0),
                "block2_x": _float_value(values, "block2_x", 0.0),
                "block2_y": _float_value(values, "block2_y", 0.0),
                "block2_center_x": _float_value(values, "block2_center_x", 0.0),
                "block2_center_y": _float_value(values, "block2_center_y", 0.0),
                "block3_x": _float_value(values, "block3_x", 0.0),
                "block3_y": _float_value(values, "block3_y", 0.0),
                "block3_center_x": _float_value(values, "block3_center_x", 0.0),
                "block3_center_y": _float_value(values, "block3_center_y", 0.0),
                "refractive_index": _float_value(values, "refractive_index", 3.4),
            },
            units={
                "sx": "um",
                "sy": "um",
                "block_x": "um",
                "block_y": "um",
                "block_center_x": "um",
                "block_center_y": "um",
                "block2_x": "um",
                "block2_y": "um",
                "block2_center_x": "um",
                "block2_center_y": "um",
                "block3_x": "um",
                "block3_y": "um",
                "block3_center_x": "um",
                "block3_center_y": "um",
            },
        )
        return SimulationTask(
            name="meep_flux_scan",
            simulator=self.simulator_kind,
            parameters={
                **geometry.parameters,
                "device_kind": device_kind,
                "cladding_index": _float_value(values, "cladding_index", 1.0),
                "input_width": _float_value(values, "input_width", 1.0),
                "output_width": _float_value(values, "output_width", 1.0),
                "arm_separation": _float_value(values, "arm_separation", 3.0),
                "input_length": _float_value(values, "input_length", 4.0),
                "output_length": _float_value(values, "output_length", 4.0),
                "route_low_port": str(values.get("route_low_port", "upper")),
                "route_high_port": str(values.get("route_high_port", "lower")),
                "resolution": _int_value(values, "resolution", 20),
                "dpml": _float_value(values, "dpml", 1.0),
                "fcen": _float_value(values, "fcen", 0.15),
                "df": _float_value(values, "df", 0.1),
                "nfreq": _int_value(values, "nfreq", 25),
                "until": _int_value(values, "until", 50),
            },
            geometry=geometry,
            expected_outputs=["meep_results.json", "stdout.log", "stderr.log"],
        )

    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]:
        template = Template(self._template_path.read_text(encoding="utf-8"))
        driver = template.render(**spec.parameters)
        driver_artifact = write_text_artifact(
            path=workdir / "run_meep.py",
            content=driver,
            artifact_type=ArtifactType.SCRIPT,
            artifact_role="python_driver",
            stage_name=spec.stage_name,
        )
        launch_script = write_text_artifact(
            path=workdir / "launch.sh",
            content=f"#!/usr/bin/env bash\nset -euo pipefail\n{self.binary_name} run_meep.py\n",
            artifact_type=ArtifactType.SCRIPT,
            artifact_role="launch_script",
            stage_name=spec.stage_name,
        )
        return [driver_artifact, launch_script]

    def build_command(self, spec: ExperimentSpec, workdir: Path) -> list[str]:
        return [self.binary_name, "run_meep.py"]

    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult:
        results_path = Path(execution.workdir_path) / "meep_results.json"
        metrics: dict[str, float] = {}
        timeseries: dict[str, list[float]] = {}
        errors: list[str] = []
        if results_path.exists():
            payload = json.loads(results_path.read_text(encoding="utf-8"))
            monitors = payload.get("monitors", {})
            transmission = [
                float(value)
                for value in (monitors.get("transmission") or payload.get("transmission") or [])
            ]
            reflection = [
                float(value)
                for value in (monitors.get("reflection") or payload.get("reflection") or [])
            ]
            upper = [float(value) for value in (monitors.get("upper") or [])]
            lower = [float(value) for value in (monitors.get("lower") or [])]
            frequencies = [float(value) for value in payload.get("frequencies", [])]
            timeseries = {
                "frequencies": frequencies,
            }
            if transmission:
                timeseries["transmission"] = transmission
            if reflection:
                timeseries["reflection"] = reflection
            if upper:
                timeseries["upper"] = upper
            if lower:
                timeseries["lower"] = lower

            metrics = {
                "transmission_peak": max(transmission) if transmission else 0.0,
                "reflection_peak": max(reflection) if reflection else 0.0,
                "transmission_mean": _mean(transmission),
                "reflection_mean": _mean(reflection),
            }
            metrics.update(
                {
                    "insertion_loss_db": _insertion_loss_db(metrics["transmission_mean"]),
                    "return_loss_db": _return_loss_db(metrics["reflection_mean"]),
                }
            )
            passband_threshold = max(0.1, 0.5 * metrics["transmission_peak"])
            metrics["passband_fraction"] = _bandwidth_fraction(
                transmission, lambda value: value >= passband_threshold
            )
            metrics["device_score"] = (
                metrics["return_loss_db"]
                - metrics["insertion_loss_db"]
                + 5.0 * metrics["passband_fraction"]
            )

            if upper or lower:
                upper_mean = _mean(upper)
                lower_mean = _mean(lower)
                combined = [
                    upper_value + lower_value
                    for upper_value, lower_value in zip(upper, lower, strict=False)
                ]
                split_denominator = upper_mean + lower_mean + 1.0e-9
                metrics.update(
                    {
                        "upper_peak": max(upper) if upper else 0.0,
                        "lower_peak": max(lower) if lower else 0.0,
                        "upper_mean": upper_mean,
                        "lower_mean": lower_mean,
                        "total_output_peak": max(combined) if combined else 0.0,
                        "total_output_mean": _mean(combined),
                        "split_imbalance": abs(upper_mean - lower_mean),
                        "split_balance": 1.0 - abs(upper_mean - lower_mean) / split_denominator,
                        "split_imbalance_db": _imbalance_db(upper_mean, lower_mean),
                        "splitter_excess_loss_db": _insertion_loss_db(_mean(combined)),
                        "splitter_score": _mean(combined)
                        * (1.0 - abs(upper_mean - lower_mean) / split_denominator),
                    }
                )
                pairwise_totals = [
                    upper_value + lower_value
                    for upper_value, lower_value in zip(upper, lower, strict=False)
                ]
                pairwise_imbalance_db = [
                    _imbalance_db(upper_value, lower_value)
                    for upper_value, lower_value in zip(upper, lower, strict=False)
                ]
                splitter_threshold = max(1.0e-6, 0.5 * metrics["total_output_peak"])
                metrics["splitter_bandwidth_fraction"] = (
                    sum(
                        1
                        for total_value, imbalance_value in zip(
                            pairwise_totals, pairwise_imbalance_db, strict=False
                        )
                        if total_value >= splitter_threshold and imbalance_value <= 1.0
                    )
                    / len(pairwise_totals)
                    if pairwise_totals
                    else 0.0
                )
                metrics["device_score"] = (
                    -metrics["splitter_excess_loss_db"]
                    - metrics["split_imbalance_db"]
                    + 0.25 * metrics["return_loss_db"]
                    + 5.0 * metrics["splitter_bandwidth_fraction"]
                )

                upper_low, upper_high = _split_halves(upper)
                lower_low, lower_high = _split_halves(lower)
                route_targets = payload.get("route_targets", {})
                low_target = str(route_targets.get("low", "upper"))
                high_target = str(route_targets.get("high", "lower"))
                low_target_series = upper_low if low_target == "upper" else lower_low
                low_off_series = lower_low if low_target == "upper" else upper_low
                high_target_series = upper_high if high_target == "upper" else lower_high
                high_off_series = lower_high if high_target == "upper" else upper_high
                target_low = _mean(upper_low) if low_target == "upper" else _mean(lower_low)
                off_low = _mean(lower_low) if low_target == "upper" else _mean(upper_low)
                target_high = _mean(upper_high) if high_target == "upper" else _mean(lower_high)
                off_high = _mean(lower_high) if high_target == "upper" else _mean(upper_high)
                metrics.update(
                    {
                        "upper_low_mean": _mean(upper_low),
                        "upper_high_mean": _mean(upper_high),
                        "lower_low_mean": _mean(lower_low),
                        "lower_high_mean": _mean(lower_high),
                        "demux_target_mean": 0.5 * (target_low + target_high),
                        "demux_leakage_mean": 0.5 * (off_low + off_high),
                        "demux_score": (target_low - off_low) + (target_high - off_high),
                        "demux_insertion_loss_db": _insertion_loss_db(
                            0.5 * (target_low + target_high)
                        ),
                        "demux_crosstalk_db": _power_db(
                            (0.5 * (off_low + off_high))
                            / max(0.5 * (target_low + target_high), 1.0e-12)
                        ),
                    }
                )
                metrics["demux_isolation_db"] = -metrics["demux_crosstalk_db"]
                routing_target_series = [*low_target_series, *high_target_series]
                routing_off_series = [*low_off_series, *high_off_series]
                routing_threshold = max(
                    1.0e-6,
                    0.5 * max(routing_target_series) if routing_target_series else 1.0e-6,
                )
                metrics["demux_bandwidth_fraction"] = (
                    sum(
                        1
                        for target_value, off_value in zip(
                            routing_target_series, routing_off_series, strict=False
                        )
                        if target_value >= routing_threshold and target_value >= 1.258925 * off_value
                    )
                    / len(routing_target_series)
                    if routing_target_series
                    else 0.0
                )
                if payload.get("device_kind") == "demux":
                    metrics["device_score"] = (
                        -metrics["demux_insertion_loss_db"]
                        + metrics["demux_isolation_db"]
                        + 0.25 * metrics["return_loss_db"]
                        + 5.0 * metrics["demux_bandwidth_fraction"]
                    )
        else:
            errors.append("missing meep_results.json")
        return SimulationParseResult(
            experiment_id=execution.experiment_id,
            campaign_id=execution.campaign_id,
            candidate_id=execution.candidate_id,
            simulator=self.simulator_kind,
            stage_name=execution.stage_name,
            status=execution.status,
            scalar_metrics=metrics,
            timeseries=timeseries,
            convergence=execution.status.value == "succeeded",
            warnings=[],
            parse_errors=errors,
            raw_output_references=[str(results_path)],
        )

    def validate_parsed(self, parsed: SimulationParseResult) -> SimulationValidationResult:
        reasons: list[str] = []
        status = "valid"
        failure_class = FailureClass.NONE
        if parsed.status.value != "succeeded":
            status = "invalid"
            failure_class = FailureClass.ENGINE
            reasons.append(f"stage status is {parsed.status.value}")
        if parsed.parse_errors:
            status = "invalid"
            failure_class = FailureClass.PARSE
            reasons.extend(parsed.parse_errors)
        if not (
            parsed.timeseries.get("transmission")
            or parsed.timeseries.get("upper")
            or parsed.timeseries.get("lower")
        ):
            status = "partial" if status == "valid" else status
            reasons.append("missing output spectrum")
        return SimulationValidationResult(
            experiment_id=parsed.experiment_id,
            campaign_id=parsed.campaign_id,
            candidate_id=parsed.candidate_id,
            simulator=self.simulator_kind,
            stage_name=parsed.stage_name,
            status=status,
            reasons=reasons,
            failure_class=failure_class,
            derived_metrics=parsed.scalar_metrics,
        )
