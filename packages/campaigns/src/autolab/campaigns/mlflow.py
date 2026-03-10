from __future__ import annotations

import mlflow
from autolab.core.models import Campaign, SimulationRun
from autolab.core.settings import Settings


def log_run(settings: Settings, campaign: Campaign, run: SimulationRun) -> None:
    mlflow.set_tracking_uri(settings.mlflow.tracking_uri)
    mlflow.set_experiment(settings.mlflow.experiment_name)
    with mlflow.start_run(run_name=str(run.id), nested=True):
        mlflow.set_tags(
            {
                "campaign_id": str(campaign.id),
                "campaign_name": campaign.name,
                "simulator": campaign.simulator.value,
                "run_status": run.status.value,
            }
        )
        mlflow.log_params(run.metadata)
        for name, value in run.metrics.items():
            mlflow.log_metric(name, value)
