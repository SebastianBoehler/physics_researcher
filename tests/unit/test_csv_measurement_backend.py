from __future__ import annotations

import json
from pathlib import Path

from autolab.core.enums import RunStatus, SimulatorKind
from autolab.core.models import SimulationExecutionRecord
from autolab.core.settings import get_settings
from autolab.simulators.csv_measurement import CSVMeasurementSimulator


def test_csv_measurement_parser_derives_thermoelectric_metrics(tmp_path: Path) -> None:
    workdir = tmp_path / "csv-measurement"
    workdir.mkdir(parents=True)
    (workdir / "measurement.csv").write_text(
        "\n".join(
            [
                "sample_id,replicate_id,temperature_k,delta_t_k,voltage_v,current_a,resistance_ohm,length_m,area_m2",
                "sample-a,1,300,10,0.0020,0.015,0.02,0.002,0.000001",
                "sample-a,2,305,10,0.0021,0.015,0.0195,0.002,0.000001",
                "sample-a,3,310,10,0.0019,0.015,0.0205,0.002,0.000001",
            ]
        ),
        encoding="utf-8",
    )
    (workdir / "measurement_ingest.json").write_text(
        json.dumps({"measurement_present": True, "byte_count": 256}),
        encoding="utf-8",
    )
    (workdir / "measurement_schema.json").write_text(
        json.dumps(
            {
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
                "min_replicates": 3,
            }
        ),
        encoding="utf-8",
    )
    execution = SimulationExecutionRecord(
        experiment_id="00000000-0000-0000-0000-000000000020",
        campaign_id="00000000-0000-0000-0000-000000000021",
        candidate_id="00000000-0000-0000-0000-000000000022",
        simulator=SimulatorKind.CSV_MEASUREMENT,
        stage_name="measurement",
        workdir_path=str(workdir),
        status=RunStatus.SUCCEEDED,
    )

    backend = CSVMeasurementSimulator(get_settings())
    parsed = backend.parse_outputs(execution)
    validation = backend.validate_parsed(parsed)

    assert parsed.scalar_metrics["replicate_count"] == 3.0
    assert parsed.scalar_metrics["seebeck_coefficient"] > 0
    assert parsed.scalar_metrics["electrical_conductivity"] > 0
    assert parsed.scalar_metrics["power_factor"] > 0
    assert validation.valid is True
