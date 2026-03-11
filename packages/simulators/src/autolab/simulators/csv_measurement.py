from __future__ import annotations

import csv
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

from autolab.core.enums import ArtifactType, FailureClass, SimulatorKind
from autolab.core.models import (
    Candidate,
    ExperimentSpec,
    SimulationArtifact,
    SimulationExecutionRecord,
    SimulationParseResult,
    SimulationTask,
    SimulationValidationResult,
)
from autolab.simulators.core.adapter import WorkflowBackedSimulator
from autolab.simulators.core.artifacts import write_json_artifact, write_text_artifact

DEFAULT_COLUMNS = [
    "sample_id",
    "replicate_id",
    "temperature_k",
    "delta_t_k",
    "voltage_v",
    "current_a",
    "resistance_ohm",
    "length_m",
    "area_m2",
]


def _candidate_values(spec: ExperimentSpec) -> dict[str, Any]:
    values = spec.provenance.get("candidate_values", {})
    return values if isinstance(values, dict) else {}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class CSVMeasurementSimulator(WorkflowBackedSimulator):
    simulator_name = "csv_measurement"
    simulator_kind = SimulatorKind.CSV_MEASUREMENT

    @property
    def binary_name(self) -> str:
        return sys.executable

    @property
    def enabled(self) -> bool:
        return True

    @property
    def timeout_seconds(self) -> int:
        return self._settings.simulators.default_timeout_seconds

    def build_task(self, candidate: Candidate) -> SimulationTask:
        return SimulationTask(
            name="csv_measurement",
            simulator=self.simulator_kind,
            parameters={
                "required_columns": DEFAULT_COLUMNS,
                "min_replicates": 3,
                "auto_generate_from_candidate": True,
            },
            expected_outputs=[
                "measurement.csv",
                "measurement_ingest.json",
                "stdout.log",
                "stderr.log",
            ],
        )

    def _required_columns(self, spec: ExperimentSpec) -> list[str]:
        value = spec.parameters.get("required_columns", DEFAULT_COLUMNS)
        if isinstance(value, list):
            return [str(item) for item in value]
        return DEFAULT_COLUMNS

    def _measurement_rows_from_candidate(self, spec: ExperimentSpec) -> list[dict[str, Any]]:
        candidate_values = _candidate_values(spec)
        dopant = float(candidate_values.get("dopant_fraction", 0.14))
        sinter = float(candidate_values.get("sinter_temperature_c", 720.0))
        anneal = float(candidate_values.get("anneal_hours", 6.0))
        sample_id = str(spec.parameters.get("sample_id", f"sample-{str(spec.candidate_id).split('-')[0]}"))
        base_seebeck = 150e-6 + 260e-6 * dopant - 60e-6 * abs(dopant - 0.18)
        conductivity = 5.5e4 + 2.5e4 * dopant + 18.0 * (sinter - 650.0) + 2200.0 * anneal
        conductivity = max(conductivity, 1.0e3)
        length_m = 2.0e-3
        area_m2 = 1.2e-6
        delta_t = 12.0
        current_a = 0.015
        rows: list[dict[str, Any]] = []
        for index, factor in enumerate((0.985, 1.0, 1.015), start=1):
            seebeck = base_seebeck * factor
            sigma = conductivity * factor
            resistance = length_m / (sigma * area_m2)
            rows.append(
                {
                    "sample_id": sample_id,
                    "replicate_id": index,
                    "temperature_k": 300.0 + 5.0 * index,
                    "delta_t_k": delta_t,
                    "voltage_v": seebeck * delta_t,
                    "current_a": current_a,
                    "resistance_ohm": resistance,
                    "length_m": length_m,
                    "area_m2": area_m2,
                }
            )
        return rows

    def _write_measurement_csv(self, path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow({column: row.get(column, "") for column in columns})

    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]:
        artifacts: list[SimulationArtifact] = []
        columns = self._required_columns(spec)
        measurement_path = workdir / "measurement.csv"
        source_path = spec.parameters.get("measurement_source_path")
        rows = spec.parameters.get("measurement_rows")
        if isinstance(source_path, str) and source_path:
            source = Path(source_path)
            if source.exists():
                measurement_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, measurement_path)
                artifacts.append(
                    SimulationArtifact(
                        artifact_type=ArtifactType.INPUT,
                        artifact_role="measurement_csv",
                        path=str(measurement_path),
                        stage_name=spec.stage_name,
                    )
                )
        elif isinstance(rows, list):
            self._write_measurement_csv(measurement_path, rows, columns)
            artifacts.append(
                SimulationArtifact(
                    artifact_type=ArtifactType.INPUT,
                    artifact_role="measurement_csv",
                    path=str(measurement_path),
                    stage_name=spec.stage_name,
                )
            )
        elif bool(spec.parameters.get("auto_generate_from_candidate")):
            generated_rows = self._measurement_rows_from_candidate(spec)
            self._write_measurement_csv(measurement_path, generated_rows, columns)
            artifacts.append(
                SimulationArtifact(
                    artifact_type=ArtifactType.INPUT,
                    artifact_role="measurement_csv",
                    path=str(measurement_path),
                    stage_name=spec.stage_name,
                    metadata={"generated": True},
                )
            )
        else:
            template = ",".join(columns) + "\n"
            artifacts.append(
                write_text_artifact(
                    path=workdir / "measurement_template.csv",
                    content=template,
                    artifact_type=ArtifactType.INPUT,
                    artifact_role="measurement_template",
                    stage_name=spec.stage_name,
                    media_type="text/csv",
                )
            )
        artifacts.append(
            write_json_artifact(
                path=workdir / "measurement_schema.json",
                payload={
                    "required_columns": columns,
                    "min_replicates": int(spec.parameters.get("min_replicates", 1)),
                },
                artifact_type=ArtifactType.METADATA,
                artifact_role="measurement_schema",
                stage_name=spec.stage_name,
            )
        )
        return artifacts

    def build_command(self, spec: ExperimentSpec, workdir: Path) -> list[str]:
        code = (
            "import json\n"
            "from pathlib import Path\n"
            "measurement = Path('measurement.csv')\n"
            "payload = {'measurement_present': measurement.exists(), 'byte_count': measurement.stat().st_size if measurement.exists() else 0}\n"
            "Path('measurement_ingest.json').write_text(json.dumps(payload), encoding='utf-8')\n"
            "raise SystemExit(0 if measurement.exists() else 1)\n"
        )
        return [self.binary_name, "-c", code]

    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult:
        measurement_path = Path(execution.workdir_path) / "measurement.csv"
        ingest_path = Path(execution.workdir_path) / "measurement_ingest.json"
        schema_path = Path(execution.workdir_path) / "measurement_schema.json"
        metrics: dict[str, float] = {}
        timeseries: dict[str, list[float]] = {}
        warnings: list[str] = []
        errors: list[str] = []
        replicate_ids: set[str] = set()
        row_count = 0
        required_columns = DEFAULT_COLUMNS
        min_replicates = 1
        if schema_path.exists():
            schema_payload = json.loads(schema_path.read_text(encoding="utf-8"))
            if isinstance(schema_payload.get("required_columns"), list):
                required_columns = [str(item) for item in schema_payload["required_columns"]]
            min_replicates = int(schema_payload.get("min_replicates", 1))
        if not measurement_path.exists():
            errors.append("missing measurement.csv")
        else:
            with measurement_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = reader.fieldnames or []
                missing_columns = [column for column in required_columns if column not in fieldnames]
                if missing_columns:
                    errors.append(f"missing required columns: {', '.join(missing_columns)}")
                seebeck_values: list[float] = []
                conductivity_values: list[float] = []
                power_factor_values: list[float] = []
                temperatures: list[float] = []
                for row in reader:
                    row_count += 1
                    replicate_ids.add(str(row.get("replicate_id", row_count)))
                    try:
                        delta_t = float(row["delta_t_k"])
                        voltage = float(row["voltage_v"])
                        resistance = float(row["resistance_ohm"])
                        length_m = float(row["length_m"])
                        area_m2 = float(row["area_m2"])
                        temperature_k = float(row["temperature_k"])
                    except (KeyError, TypeError, ValueError) as exc:
                        errors.append(f"row {row_count}: {exc}")
                        continue
                    if math.isclose(delta_t, 0.0):
                        errors.append(f"row {row_count}: delta_t_k must be non-zero")
                        continue
                    if math.isclose(resistance * area_m2, 0.0):
                        errors.append(f"row {row_count}: resistance_ohm * area_m2 must be non-zero")
                        continue
                    seebeck = voltage / delta_t
                    conductivity = length_m / (resistance * area_m2)
                    power_factor = (seebeck**2) * conductivity
                    seebeck_values.append(seebeck)
                    conductivity_values.append(conductivity)
                    power_factor_values.append(power_factor)
                    temperatures.append(temperature_k)
                metrics = {
                    "seebeck_coefficient": _mean(seebeck_values),
                    "electrical_conductivity": _mean(conductivity_values),
                    "power_factor": _mean(power_factor_values),
                    "replicate_count": float(len(replicate_ids)),
                    "measurement_row_count": float(row_count),
                }
                timeseries = {
                    "temperature_k": temperatures,
                    "power_factor": power_factor_values,
                }
        if ingest_path.exists():
            payload = json.loads(ingest_path.read_text(encoding="utf-8"))
            if not payload.get("measurement_present"):
                warnings.append("measurement ingest marked file as absent")
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
            warnings=warnings,
            parse_errors=errors,
            raw_output_references=[str(measurement_path), str(ingest_path), str(schema_path)],
            metadata={
                "replicate_ids": sorted(replicate_ids),
                "min_replicates": min_replicates,
                "required_columns": required_columns,
            },
        )

    def validate_parsed(self, parsed: SimulationParseResult) -> SimulationValidationResult:
        status = "valid"
        reasons: list[str] = []
        failure_class = FailureClass.NONE
        if parsed.status.value != "succeeded":
            status = "invalid"
            failure_class = FailureClass.ENGINE
            reasons.append(f"stage status is {parsed.status.value}")
        if parsed.parse_errors:
            status = "invalid"
            failure_class = FailureClass.PARSE
            reasons.extend(parsed.parse_errors)
        min_replicates = int(parsed.metadata.get("min_replicates", 0)) if isinstance(parsed.metadata, dict) else 0
        replicate_count = int(parsed.scalar_metrics.get("replicate_count", 0.0))
        if min_replicates and replicate_count < min_replicates:
            status = "invalid"
            failure_class = FailureClass.VALIDATION
            reasons.append(
                f"replicate_count {replicate_count} is below required minimum {min_replicates}"
            )
        if not parsed.scalar_metrics.get("power_factor"):
            status = "partial" if status == "valid" else status
            reasons.append("power_factor could not be derived from the measurement rows")
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
