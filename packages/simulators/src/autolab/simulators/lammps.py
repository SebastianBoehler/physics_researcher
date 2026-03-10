from __future__ import annotations

import re
from pathlib import Path

from autolab.core.enums import ArtifactType, FailureClass, RunStatus, SimulatorKind
from autolab.core.models import (
    Candidate,
    ExperimentSpec,
    SimulationArtifact,
    SimulationExecutionRecord,
    SimulationParseResult,
    SimulationTask,
    SimulationValidationResult,
    SimulationWorkflow,
)
from autolab.core.settings import Settings
from autolab.simulators.core.adapter import WorkflowBackedSimulator
from autolab.simulators.core.artifacts import copy_file_artifact, write_text_artifact
from jinja2 import Template

_LOOP_TIME_PATTERN = re.compile(
    r"Loop time of (?P<loop_time>[-+0-9.eE]+) on (?P<procs>\d+) procs "
    r"for (?P<steps>\d+) steps with (?P<atoms>\d+) atoms"
)
_WARNING_PATTERN = re.compile(r"^\s*WARNING:\s*(?P<message>.+)$", re.MULTILINE)
_ERROR_PATTERN = re.compile(r"^\s*ERROR:\s*(?P<message>.+)$", re.MULTILINE)
_ATOM_COUNT_PATTERN = re.compile(r"(?:Created|with)\s+(?P<atoms>\d+)\s+atoms")


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _extract_last_float_series(columns: dict[str, list[float]], key: str) -> float:
    return columns.get(key, [0.0])[-1] if columns.get(key) else 0.0


def _parse_lammps_thermo(
    text: str,
) -> tuple[
    dict[str, float], dict[str, list[float]], dict[str, float | int | bool], list[str], list[str]
]:
    headers: list[str] | None = None
    current_rows: list[list[float]] = []
    sections: list[tuple[list[str], list[list[float]]]] = []

    def _flush_section() -> None:
        nonlocal headers, current_rows
        if headers and current_rows:
            sections.append((headers, current_rows))
        headers = None
        current_rows = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            _flush_section()
            continue
        tokens = line.split()
        if {"Step", "Temp"}.issubset(tokens):
            _flush_section()
            headers = tokens
            continue
        if headers is None:
            continue
        if len(tokens) != len(headers):
            _flush_section()
            continue
        try:
            current_rows.append([float(token) for token in tokens])
        except ValueError:
            _flush_section()
    _flush_section()

    warnings = [match.group("message").strip() for match in _WARNING_PATTERN.finditer(text)]
    errors = [match.group("message").strip() for match in _ERROR_PATTERN.finditer(text)]
    if not sections:
        errors.append("no thermodynamic block found in LAMMPS output")
        metadata = {
            "thermo_sections": 0,
            "thermo_rows": 0,
            "completion_detected": False,
        }
        return {}, {}, metadata, warnings, errors

    section_headers = [tuple(header.lower() for header in header_row) for header_row, _ in sections]
    canonical_headers = section_headers[-1]
    if any(header_row != canonical_headers for header_row in section_headers[:-1]):
        warnings.append("multiple thermo styles detected; using final thermo block schema")

    merged_columns: dict[str, list[float]] = {header: [] for header in canonical_headers}
    for headers_row, rows in sections:
        lowered = [header.lower() for header in headers_row]
        if tuple(lowered) != canonical_headers:
            continue
        for index, header in enumerate(lowered):
            merged_columns[header].extend(row[index] for row in rows)

    loop_match = _LOOP_TIME_PATTERN.search(text)
    atom_match = _ATOM_COUNT_PATTERN.search(text)
    loop_time_seconds = float(loop_match.group("loop_time")) if loop_match else None
    atom_count = (
        int(loop_match.group("atoms"))
        if loop_match
        else int(atom_match.group("atoms"))
        if atom_match
        else None
    )
    step_count = int(loop_match.group("steps")) if loop_match else None
    process_count = int(loop_match.group("procs")) if loop_match else None

    metrics = {
        "step": _extract_last_float_series(merged_columns, "step"),
        "temperature": _extract_last_float_series(merged_columns, "temp"),
        "pressure": _extract_last_float_series(merged_columns, "press"),
        "potential_energy": _extract_last_float_series(merged_columns, "pe"),
        "kinetic_energy": _extract_last_float_series(merged_columns, "ke"),
        "total_energy": _extract_last_float_series(merged_columns, "etotal"),
        "volume": _extract_last_float_series(merged_columns, "vol"),
        "density": _extract_last_float_series(merged_columns, "density"),
        "temperature_mean": _mean(merged_columns.get("temp", [])),
        "pressure_mean": _mean(merged_columns.get("press", [])),
        "potential_energy_mean": _mean(merged_columns.get("pe", [])),
        "thermo_rows": float(sum(len(rows) for _, rows in sections)),
    }
    if loop_time_seconds is not None:
        metrics["loop_time_seconds"] = loop_time_seconds
    if atom_count is not None:
        metrics["atom_count"] = float(atom_count)

    metadata: dict[str, float | int | bool] = {
        "thermo_sections": len(sections),
        "thermo_rows": int(metrics["thermo_rows"]),
        "completion_detected": loop_match is not None,
    }
    if step_count is not None:
        metadata["reported_steps"] = step_count
    if process_count is not None:
        metadata["process_count"] = process_count
    if atom_count is not None:
        metadata["atom_count"] = atom_count
    return metrics, merged_columns, metadata, warnings, errors


class LammpsSimulator(WorkflowBackedSimulator):
    simulator_name = "lammps"
    simulator_kind = SimulatorKind.LAMMPS

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._template_path = (
            Path(__file__).resolve().parent / "templates" / "lammps" / "in.lammps.j2"
        )

    @property
    def binary_name(self) -> str:
        return self._settings.simulators.lammps_bin

    @property
    def enabled(self) -> bool:
        return self._settings.simulators.enable_lammps

    @property
    def timeout_seconds(self) -> int:
        return self._settings.simulators.lammps_timeout_seconds

    @property
    def command_wrapper(self) -> str | None:
        return self._settings.simulators.lammps_wrapper

    @property
    def environment_overrides(self) -> dict[str, str]:
        return self._settings.simulators.lammps_environment

    def build_task(self, candidate: Candidate) -> SimulationTask:
        temperature = float(candidate.values.get("temperature", 1.0))
        initialization_mode = str(
            candidate.metadata.get(
                "lammps_initialization_mode",
                "data_file" if candidate.metadata.get("lammps_data_file") else "generated_lattice",
            )
        )
        data_file = str(candidate.metadata.get("lammps_data_file", "")).strip()
        ensemble = str(candidate.values.get("ensemble", "nve")).lower()
        parameters = {
            "steps": int(candidate.values.get("steps", 100)),
            "temperature": temperature,
            "start_temperature": float(candidate.values.get("start_temperature", temperature)),
            "target_temperature": float(candidate.values.get("target_temperature", temperature)),
            "pressure_target": float(candidate.values.get("pressure_target", 0.0)),
            "thermostat_damping": float(candidate.values.get("thermostat_damping", 1.0)),
            "barostat_damping": float(candidate.values.get("barostat_damping", 5.0)),
            "lattice_constant": float(candidate.values.get("lattice_constant", 0.8442)),
            "box_extent": float(candidate.values.get("box_extent", 4)),
            "mass": float(candidate.values.get("mass", 1.0)),
            "epsilon": float(candidate.values.get("epsilon", 1.0)),
            "sigma": float(candidate.values.get("sigma", 1.0)),
            "cutoff": float(candidate.values.get("cutoff", 2.5)),
            "seed": int(candidate.metadata.get("seed", 42)),
            "units_style": str(candidate.values.get("units_style", "lj")),
            "dimension": int(candidate.values.get("dimension", 3)),
            "boundary": str(candidate.values.get("boundary", "p p p")),
            "lattice_style": str(candidate.values.get("lattice_style", "sc")),
            "atom_style": str(candidate.values.get("atom_style", "atomic")),
            "atom_type_count": int(candidate.values.get("atom_type_count", 1)),
            "timestep": float(candidate.values.get("timestep", 0.005)),
            "thermo_frequency": int(candidate.values.get("thermo_frequency", 10)),
            "dump_frequency": int(candidate.values.get("dump_frequency", 0)),
            "neighbor_skin": float(candidate.values.get("neighbor_skin", 0.3)),
            "neighbor_bin": str(candidate.values.get("neighbor_bin", "bin")),
            "neigh_modify_every": int(candidate.values.get("neigh_modify_every", 1)),
            "ensemble": ensemble,
            "create_velocity": _as_bool(
                candidate.values.get("create_velocity", True), default=True
            ),
            "initialization_mode": initialization_mode,
            "data_file_name": Path(data_file).name if data_file else "",
        }
        return SimulationTask(
            name="lammps_md",
            simulator=self.simulator_kind,
            parameters=parameters,
            units={
                "temperature": "lj",
                "start_temperature": "lj",
                "target_temperature": "lj",
                "pressure_target": "lj",
                "lattice_constant": "lj",
                "box_extent": "lattice_units",
                "timestep": "tau",
                "thermostat_damping": "tau",
                "barostat_damping": "tau",
            },
            expected_outputs=["log.lammps", "stdout.log", "stderr.log"],
            metadata={"source_data_file": data_file, "initialization_mode": initialization_mode},
        )

    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]:
        template = Template(self._template_path.read_text(encoding="utf-8"))
        input_text = template.render(**spec.parameters)
        artifacts: list[SimulationArtifact] = [
            write_text_artifact(
                path=workdir / "in.lammps",
                content=input_text,
                artifact_type=ArtifactType.INPUT,
                artifact_role="input_deck",
                stage_name=spec.stage_name,
            )
        ]
        source_data_file = str(spec.metadata.get("lammps_data_file", "")).strip()
        if spec.parameters.get("initialization_mode") == "data_file":
            if not source_data_file:
                msg = "LAMMPS data_file mode requires candidate.metadata['lammps_data_file']"
                raise ValueError(msg)
            source_path = Path(source_data_file)
            if not source_path.exists():
                msg = f"LAMMPS data file does not exist: {source_path}"
                raise FileNotFoundError(msg)
            artifacts.append(
                copy_file_artifact(
                    source=source_path,
                    destination=workdir / source_path.name,
                    artifact_type=ArtifactType.INPUT,
                    artifact_role="input_data_file",
                    stage_name=spec.stage_name,
                )
            )
        launch_script = write_text_artifact(
            path=workdir / "launch.sh",
            content=(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                f"{self.binary_name} -in in.lammps -log log.lammps\n"
            ),
            artifact_type=ArtifactType.SCRIPT,
            artifact_role="launch_script",
            stage_name=spec.stage_name,
        )
        artifacts.append(launch_script)
        return artifacts

    def create_experiment_spec(
        self,
        candidate: Candidate,
        workflow: SimulationWorkflow | None = None,
        stage_name: str = "primary",
    ) -> ExperimentSpec:
        spec = super().create_experiment_spec(candidate, workflow=workflow, stage_name=stage_name)
        if candidate.metadata.get("lammps_data_file"):
            spec.metadata["lammps_data_file"] = str(candidate.metadata["lammps_data_file"])
        return spec

    def build_command(self, spec: ExperimentSpec, workdir: Path) -> list[str]:
        return [self.binary_name, "-in", str(workdir / "in.lammps"), "-log", "log.lammps"]

    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult:
        workdir = Path(execution.workdir_path)
        log_path = workdir / "log.lammps"
        stdout_path = workdir / "stdout.log"
        raw_path = log_path if log_path.exists() else stdout_path
        text = raw_path.read_text(encoding="utf-8") if raw_path.exists() else ""
        metrics, columns, metadata, warnings, errors = _parse_lammps_thermo(text)
        if not log_path.exists():
            warnings.append("log.lammps not found; parser fell back to stdout.log")
        if execution.status == RunStatus.TIMED_OUT:
            warnings.append("LAMMPS execution timed out before clean completion")
        return SimulationParseResult(
            experiment_id=execution.experiment_id,
            campaign_id=execution.campaign_id,
            candidate_id=execution.candidate_id,
            simulator=self.simulator_kind,
            stage_name=execution.stage_name,
            status=execution.status,
            scalar_metrics=metrics,
            timeseries=dict(columns),
            convergence=bool(metadata.get("completion_detected")) and not errors,
            warnings=warnings,
            parse_errors=errors,
            raw_output_references=[str(raw_path)],
            metadata={
                **metadata,
                "log_path_exists": log_path.exists(),
                "stdout_path_exists": stdout_path.exists(),
            },
        )

    def validate_parsed(self, parsed: SimulationParseResult) -> SimulationValidationResult:
        reasons: list[str] = []
        status = "valid"
        failure_class = FailureClass.NONE

        if parsed.status == RunStatus.TIMED_OUT:
            reasons.append("stage timed out")
            status = "invalid"
            failure_class = FailureClass.TIMEOUT
        elif parsed.status != RunStatus.SUCCEEDED:
            reasons.append(f"stage status is {parsed.status.value}")
            status = "invalid"
            failure_class = FailureClass.ENGINE

        if not parsed.metadata.get("log_path_exists", False):
            reasons.append("missing log.lammps output")
            status = "invalid"
            failure_class = FailureClass.PARSE

        if parsed.parse_errors:
            reasons.extend(parsed.parse_errors)
            status = "invalid"
            failure_class = FailureClass.PARSE

        thermo_rows = int(parsed.metadata.get("thermo_rows", 0))
        if thermo_rows == 0:
            reasons.append("no thermo rows parsed from LAMMPS output")
            status = "invalid"
            failure_class = FailureClass.PARSE

        if status == "valid" and not parsed.convergence:
            reasons.append("LAMMPS completion marker not found in output")
            status = "partial"

        return SimulationValidationResult(
            experiment_id=parsed.experiment_id,
            campaign_id=parsed.campaign_id,
            candidate_id=parsed.candidate_id,
            simulator=self.simulator_kind,
            stage_name=parsed.stage_name,
            status=status,
            reasons=reasons,
            failure_class=failure_class,
            retryable=failure_class in {FailureClass.TRANSIENT, FailureClass.TIMEOUT},
            derived_metrics=parsed.scalar_metrics,
            metadata={
                "thermo_rows": thermo_rows,
                "completion_detected": parsed.metadata.get("completion_detected", False),
            },
        )
