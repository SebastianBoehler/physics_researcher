from __future__ import annotations

import json
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


def _candidate_values(spec: ExperimentSpec) -> dict[str, Any]:
    values = spec.provenance.get("candidate_values", {})
    return values if isinstance(values, dict) else {}


class ManualProtocolSimulator(WorkflowBackedSimulator):
    simulator_name = "manual_protocol"
    simulator_kind = SimulatorKind.MANUAL_PROTOCOL

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
            name="manual_protocol",
            simulator=self.simulator_kind,
            parameters={
                "material_family": str(candidate.values.get("material_family", "thermoelectric")),
                "sample_id_template": str(
                    candidate.values.get("sample_id_template", "sample-{candidate_id_short}")
                ),
                "process_temperature_c": float(
                    candidate.values.get("sinter_temperature_c", 720.0)
                ),
                "dwell_time_hours": float(candidate.values.get("anneal_hours", 6.0)),
                "atmosphere": str(candidate.values.get("atmosphere", "argon")),
                "required_materials": ["precursor_powder", "binder", "die_set"],
            },
            units={
                "process_temperature_c": "celsius",
                "dwell_time_hours": "hour",
            },
            expected_outputs=["protocol.md", "recipe.json", "handoff.json", "stdout.log", "stderr.log"],
        )

    def _sample_id(self, spec: ExperimentSpec) -> str:
        template = str(spec.parameters.get("sample_id_template", "sample-{candidate_id_short}"))
        values = {
            "campaign_id": str(spec.campaign_id),
            "candidate_id": str(spec.candidate_id),
            "candidate_id_short": str(spec.candidate_id).split("-")[0],
            "stage_name": spec.stage_name,
        }
        try:
            return template.format_map(values)
        except (KeyError, ValueError):
            return f"sample-{values['candidate_id_short']}"

    def generate_inputs(self, spec: ExperimentSpec, workdir: Path) -> list[SimulationArtifact]:
        candidate_values = _candidate_values(spec)
        sample_id = self._sample_id(spec)
        required_materials = spec.parameters.get("required_materials", [])
        if not isinstance(required_materials, list):
            required_materials = [str(required_materials)]
        recipe = {
            "sample_id": sample_id,
            "material_family": spec.parameters.get("material_family", "thermoelectric"),
            "process_temperature_c": float(spec.parameters.get("process_temperature_c", 720.0)),
            "dwell_time_hours": float(spec.parameters.get("dwell_time_hours", 6.0)),
            "atmosphere": str(spec.parameters.get("atmosphere", "argon")),
            "required_materials": [str(item) for item in required_materials],
            "candidate_values": candidate_values,
        }
        protocol = "\n".join(
            [
                f"# Fabrication Protocol: {sample_id}",
                "",
                f"Material family: {recipe['material_family']}",
                f"Process temperature: {recipe['process_temperature_c']} C",
                f"Dwell time: {recipe['dwell_time_hours']} h",
                f"Atmosphere: {recipe['atmosphere']}",
                "",
                "Candidate parameters:",
                *[
                    f"- {key}: {value}"
                    for key, value in sorted(candidate_values.items())
                ],
                "",
                "Required materials:",
                *[f"- {item}" for item in recipe["required_materials"]],
                "",
                "Operator checklist:",
                "- Verify powder composition and mass.",
                "- Confirm furnace setpoint and atmosphere.",
                "- Label the sample before measurement handoff.",
            ]
        )
        handoff = {
            "sample_id": sample_id,
            "next_stage": "csv_measurement",
            "required_columns": [
                "sample_id",
                "replicate_id",
                "temperature_k",
                "delta_t_k",
                "voltage_v",
                "current_a",
                "resistance_ohm",
                "length_m",
                "area_m2",
            ],
        }
        return [
            write_text_artifact(
                path=workdir / "protocol.md",
                content=protocol,
                artifact_type=ArtifactType.REPORT,
                artifact_role="fabrication_protocol",
                stage_name=spec.stage_name,
            ),
            write_json_artifact(
                path=workdir / "recipe.json",
                payload=recipe,
                artifact_type=ArtifactType.METADATA,
                artifact_role="fabrication_recipe",
                stage_name=spec.stage_name,
            ),
            write_json_artifact(
                path=workdir / "handoff.json",
                payload=handoff,
                artifact_type=ArtifactType.METADATA,
                artifact_role="measurement_handoff",
                stage_name=spec.stage_name,
            ),
        ]

    def build_command(self, spec: ExperimentSpec, workdir: Path) -> list[str]:
        payload = {
            "protocol_generated": True,
            "sample_id": self._sample_id(spec),
            "candidate_parameter_count": len(_candidate_values(spec)),
        }
        code = (
            "import json\n"
            "from pathlib import Path\n"
            f"Path('manual_protocol_results.json').write_text({json.dumps(json.dumps(payload))}, "
            "encoding='utf-8')\n"
        )
        return [self.binary_name, "-c", code]

    def parse_outputs(self, execution: SimulationExecutionRecord) -> SimulationParseResult:
        results_path = Path(execution.workdir_path) / "manual_protocol_results.json"
        recipe_path = Path(execution.workdir_path) / "recipe.json"
        metrics: dict[str, float] = {}
        warnings: list[str] = []
        errors: list[str] = []
        sample_id = ""
        if results_path.exists():
            payload = json.loads(results_path.read_text(encoding="utf-8"))
            sample_id = str(payload.get("sample_id", ""))
            metrics = {
                "protocol_generated": 1.0 if payload.get("protocol_generated") else 0.0,
                "candidate_parameter_count": float(payload.get("candidate_parameter_count", 0)),
            }
        else:
            errors.append("missing manual_protocol_results.json")
        if not recipe_path.exists():
            errors.append("missing recipe.json")
        return SimulationParseResult(
            experiment_id=execution.experiment_id,
            campaign_id=execution.campaign_id,
            candidate_id=execution.candidate_id,
            simulator=self.simulator_kind,
            stage_name=execution.stage_name,
            status=execution.status,
            scalar_metrics=metrics,
            convergence=execution.status.value == "succeeded",
            warnings=warnings,
            parse_errors=errors,
            raw_output_references=[str(results_path), str(recipe_path)],
            metadata={"sample_id": sample_id},
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
