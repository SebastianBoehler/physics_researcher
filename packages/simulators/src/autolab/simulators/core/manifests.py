from __future__ import annotations

from pathlib import Path

from autolab.core.enums import ArtifactType
from autolab.core.models import ExperimentSpec, SimulationArtifact, SimulationExecutionRecord
from autolab.simulators.core.artifacts import file_sha256, write_json_artifact


def write_manifest(
    spec: ExperimentSpec,
    execution: SimulationExecutionRecord,
    artifacts: list[SimulationArtifact],
    workdir: Path,
) -> SimulationArtifact:
    inventory = [
        {
            "path": artifact.path,
            "artifact_type": artifact.artifact_type.value,
            "artifact_role": artifact.artifact_role,
            "sha256": artifact.sha256,
            "media_type": artifact.media_type,
        }
        for artifact in artifacts
    ]
    for file_path in execution.output_files:
        path = Path(file_path)
        inventory.append(
            {
                "path": file_path,
                "artifact_type": ArtifactType.OUTPUT.value,
                "artifact_role": "collected_output",
                "sha256": file_sha256(path) if path.exists() else None,
                "media_type": "application/octet-stream",
            }
        )
    payload = {
        "experiment_id": str(spec.id),
        "campaign_id": str(spec.campaign_id),
        "candidate_id": str(spec.candidate_id),
        "workflow_name": spec.workflow_name,
        "stage_name": spec.stage_name,
        "simulator": spec.simulator.value,
        "simulator_version": execution.simulator_version,
        "command": execution.command,
        "environment": execution.environment,
        "workdir": execution.workdir_path,
        "status": execution.status.value,
        "exit_code": execution.exit_code,
        "message": execution.message,
        "started_at": execution.started_at,
        "ended_at": execution.ended_at,
        "file_inventory": inventory,
        "hashes": {
            "input_sha256": execution.metadata.get("input_sha256"),
            "output_sha256": execution.metadata.get("output_sha256"),
        },
        "provenance": spec.provenance,
        "metadata": spec.metadata,
    }
    return write_json_artifact(
        path=workdir / "manifest.json",
        payload=payload,
        artifact_type=ArtifactType.MANIFEST,
        artifact_role="stage_manifest",
        stage_name=spec.stage_name,
    )
