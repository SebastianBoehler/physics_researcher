from __future__ import annotations

import json
import math
import shlex
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


def _task_name(spec: ExperimentSpec) -> str:
    return spec.workflow.stage_map()[spec.stage_name].task.name


def _driver_filename(task_name: str) -> str:
    return "run_meep_adjoint.py" if task_name == "meep_adjoint_device" else "run_meep.py"


class MeepSimulator(WorkflowBackedSimulator):
    simulator_name = "meep"
    simulator_kind = SimulatorKind.MEEP

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._template_path = (
            Path(__file__).resolve().parent / "templates" / "meep" / "run_meep.py.j2"
        )
        self._adjoint_template_path = (
            Path(__file__).resolve().parent / "templates" / "meep" / "run_meep_adjoint.py.j2"
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
        optimization_mode = str(values.get("optimization_mode", "flux"))
        task_name = "meep_adjoint_device" if optimization_mode == "adjoint" else "meep_flux_scan"
        default_device_kind = "adjoint_splitter" if task_name == "meep_adjoint_device" else "waveguide_block"
        device_kind = str(values.get("device_kind", default_device_kind))
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
                "design_region_x": _float_value(values, "design_region_x", 3.0),
                "design_region_y": _float_value(values, "design_region_y", 2.4),
                "design_region_center_x": _float_value(values, "design_region_center_x", 0.0),
                "design_region_center_y": _float_value(values, "design_region_center_y", 0.0),
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
                "design_region_x": "um",
                "design_region_y": "um",
                "design_region_center_x": "um",
                "design_region_center_y": "um",
            },
        )
        return SimulationTask(
            name=task_name,
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
                "design_resolution": _int_value(values, "design_resolution", 20),
                "adjoint_iterations": _int_value(values, "adjoint_iterations", 12),
                "step_size": _float_value(values, "step_size", 0.08),
                "minimum_feature_size": _float_value(values, "minimum_feature_size", 0.12),
                "beta_start": _float_value(values, "beta_start", 2.0),
                "beta_scale": _float_value(values, "beta_scale", 1.35),
                "beta_max": _float_value(values, "beta_max", 14.0),
                "eta": _float_value(values, "eta", 0.5),
                "imbalance_weight": _float_value(values, "imbalance_weight", 0.25),
            },
            geometry=geometry,
            expected_outputs=(
                ["adjoint_results.json", "stdout.log", "stderr.log"]
                if task_name == "meep_adjoint_device"
                else ["meep_results.json", "stdout.log", "stderr.log"]
            ),
        )

    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]:
        task_name = _task_name(spec)
        template_path = (
            self._adjoint_template_path if task_name == "meep_adjoint_device" else self._template_path
        )
        template = Template(template_path.read_text(encoding="utf-8"))
        driver = template.render(**spec.parameters)
        driver_filename = _driver_filename(task_name)
        driver_artifact = write_text_artifact(
            path=workdir / driver_filename,
            content=driver,
            artifact_type=ArtifactType.SCRIPT,
            artifact_role="python_driver",
            stage_name=spec.stage_name,
        )
        launch_content = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"{shlex.quote(self.binary_name)} {driver_filename}\n"
        )
        if task_name == "meep_adjoint_device":
            launch_content = (
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "status=0\n"
                f"{shlex.quote(self.binary_name)} {driver_filename} || status=$?\n"
                "if [[ ${status} -ne 0 && ! -f adjoint_results.json ]]; then\n"
                "cat > adjoint_error.json <<EOF\n"
                "{\n"
                '  "status": "failed",\n'
                '  "driver": "run_meep_adjoint.py",\n'
                '  "exit_code": '"${status}"',\n'
                '  "message": "Adjoint MEEP driver exited before producing adjoint_results.json. Inspect stderr.log for the native failure."\n'
                "}\n"
                "EOF\n"
                "fi\n"
                "exit ${status}\n"
            )
        launch_script = write_text_artifact(
            path=workdir / "launch.sh",
            content=launch_content,
            artifact_type=ArtifactType.SCRIPT,
            artifact_role="launch_script",
            stage_name=spec.stage_name,
        )
        return [driver_artifact, launch_script]

    def build_command(self, spec: ExperimentSpec, workdir: Path) -> list[str]:
        return ["bash", "launch.sh"]

    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult:
        adjoint_results_path = Path(execution.workdir_path) / "adjoint_results.json"
        adjoint_error_path = Path(execution.workdir_path) / "adjoint_error.json"
        results_path = Path(execution.workdir_path) / "meep_results.json"
        stderr_path = Path(execution.workdir_path) / "stderr.log"
        metrics: dict[str, float] = {}
        timeseries: dict[str, list[float]] = {}
        errors: list[str] = []
        task_name = "meep_flux_scan"
        raw_references: list[str] = []
        runtime_blocker: str | None = None
        adjoint_exit_code: int | None = None
        if adjoint_results_path.exists():
            task_name = "meep_adjoint_device"
            payload = json.loads(adjoint_results_path.read_text(encoding="utf-8"))
            metrics, timeseries = self._parse_meep_payload(payload, allow_missing_reflection=True)
            raw_references.append(str(adjoint_results_path))
            objective_history = [float(value) for value in payload.get("objective_history", [])]
            beta_history = [float(value) for value in payload.get("beta_history", [])]
            gradient_history = [float(value) for value in payload.get("gradient_norm_history", [])]
            if objective_history:
                timeseries["objective_history"] = objective_history
                metrics["adjoint_final_objective"] = objective_history[-1]
                metrics["adjoint_best_objective"] = max(objective_history)
                metrics["adjoint_iteration_count"] = float(len(objective_history))
            if beta_history:
                timeseries["beta_history"] = beta_history
                metrics["adjoint_final_beta"] = beta_history[-1]
            if gradient_history:
                timeseries["gradient_norm_history"] = gradient_history
                metrics["adjoint_final_gradient_norm"] = gradient_history[-1]
            density = [float(value) for value in payload.get("final_design_weights", [])]
            if density:
                metrics["design_fill_fraction"] = _mean(density)
                metrics["design_binary_fraction"] = sum(
                    1 for value in density if value <= 0.1 or value >= 0.9
                ) / len(density)
        elif adjoint_error_path.exists():
            task_name = "meep_adjoint_device"
            payload = json.loads(adjoint_error_path.read_text(encoding="utf-8"))
            raw_references.append(str(adjoint_error_path))
            runtime_blocker = payload.get("message")
            adjoint_exit_code = payload.get("exit_code")
            if stderr_path.exists():
                stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
                if "Assertion failed: (changed_materials)" in stderr_text:
                    runtime_blocker = (
                        "Native MEEP abort while stepping adjoint sources with DFT field "
                        "monitors (`changed_materials` assertion in `step_db`). Inspect "
                        "stderr.log for details."
                    )
        elif results_path.exists():
            payload = json.loads(results_path.read_text(encoding="utf-8"))
            metrics, timeseries = self._parse_meep_payload(payload)
            raw_references.append(str(results_path))
        else:
            errors.append("missing meep_results.json or adjoint_results.json")
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
            raw_output_references=raw_references,
            metadata={
                "task_name": task_name,
                "adjoint_runtime_blocker": runtime_blocker,
                "adjoint_exit_code": adjoint_exit_code,
            },
        )

    def validate_parsed(self, parsed: SimulationParseResult) -> SimulationValidationResult:
        reasons: list[str] = []
        status = "valid"
        failure_class = FailureClass.NONE
        if parsed.status.value != "succeeded":
            status = "invalid"
            failure_class = FailureClass.ENGINE
            reasons.append(f"stage status is {parsed.status.value}")
        if parsed.metadata.get("adjoint_runtime_blocker"):
            reasons.append(str(parsed.metadata["adjoint_runtime_blocker"]))
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
        if parsed.metadata.get("task_name") == "meep_adjoint_device" and not parsed.timeseries.get(
            "objective_history"
        ):
            status = "partial" if status == "valid" else status
            reasons.append("missing adjoint objective history")
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

    def _parse_meep_payload(
        self,
        payload: dict[str, Any],
        *,
        allow_missing_reflection: bool = False,
    ) -> tuple[dict[str, float], dict[str, list[float]]]:
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
        timeseries: dict[str, list[float]] = {"frequencies": frequencies}
        if transmission:
            timeseries["transmission"] = transmission
        if reflection:
            timeseries["reflection"] = reflection
        if upper:
            timeseries["upper"] = upper
        if lower:
            timeseries["lower"] = lower

        metrics: dict[str, float] = {
            "transmission_peak": max(transmission) if transmission else 0.0,
            "reflection_peak": max(reflection) if reflection else 0.0,
            "transmission_mean": _mean(transmission),
            "reflection_mean": _mean(reflection),
        }
        if reflection or not allow_missing_reflection:
            metrics["return_loss_db"] = _return_loss_db(metrics["reflection_mean"])
        else:
            metrics["return_loss_db"] = 0.0
        metrics["insertion_loss_db"] = _insertion_loss_db(metrics["transmission_mean"])

        passband_threshold = max(0.1, 0.5 * metrics["transmission_peak"])
        metrics["passband_fraction"] = _bandwidth_fraction(
            transmission, lambda value: value >= passband_threshold
        )
        metrics["device_score"] = (
            metrics["return_loss_db"] - metrics["insertion_loss_db"] + 5.0 * metrics["passband_fraction"]
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
        return metrics, timeseries
