from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import uvicorn
from autolab.api.dependencies import (
    get_artifact_service,
    get_campaign_service,
    get_queue,
    get_run_service,
    require_admin_token,
)
from autolab.api.schemas import (
    CampaignResponse,
    CreateCampaignRequest,
    HealthResponse,
    RunListResponse,
    StepCampaignRequest,
    StepCampaignResponse,
)
from autolab.campaigns import (
    ArtifactService,
    CampaignEvent,
    CampaignQueue,
    CampaignService,
    RunService,
)
from autolab.core.models import ArtifactRecord, Campaign, SimulationRun
from autolab.core.settings import get_settings
from autolab.telemetry import setup_logging
from fastapi import Depends, FastAPI, HTTPException, status


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    get_settings().ensure_directories()
    yield


app = FastAPI(title="Autolab API", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        services={
            "api": "ok",
            "database": "configured",
            "redis": "configured",
            "mlflow": "configured",
        },
    )


@app.post("/campaigns", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    request: CreateCampaignRequest,
    _: str = Depends(require_admin_token),
    service: CampaignService = Depends(get_campaign_service),
) -> CampaignResponse:
    campaign = Campaign(**request.model_dump())
    created = service.create_campaign(campaign)
    return CampaignResponse(
        id=created.id,
        name=created.name,
        status=created.status,
        simulator=created.simulator,
        mode=created.mode,
        budget=created.budget,
        tags=created.tags,
    )


@app.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: UUID,
    _: str = Depends(require_admin_token),
    service: CampaignService = Depends(get_campaign_service),
) -> CampaignResponse:
    campaign = service.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        simulator=campaign.simulator,
        mode=campaign.mode,
        budget=campaign.budget,
        tags=campaign.tags,
    )


@app.post("/campaigns/{campaign_id}/start", response_model=CampaignResponse)
def start_campaign(
    campaign_id: UUID,
    _: str = Depends(require_admin_token),
    service: CampaignService = Depends(get_campaign_service),
) -> CampaignResponse:
    campaign = service.start_campaign(campaign_id)
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        simulator=campaign.simulator,
        mode=campaign.mode,
        budget=campaign.budget,
        tags=campaign.tags,
    )


@app.post("/campaigns/{campaign_id}/stop", response_model=CampaignResponse)
def stop_campaign(
    campaign_id: UUID,
    _: str = Depends(require_admin_token),
    service: CampaignService = Depends(get_campaign_service),
) -> CampaignResponse:
    campaign = service.stop_campaign(campaign_id)
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        simulator=campaign.simulator,
        mode=campaign.mode,
        budget=campaign.budget,
        tags=campaign.tags,
    )


@app.get("/campaigns/{campaign_id}/runs", response_model=RunListResponse)
def list_runs(
    campaign_id: UUID,
    _: str = Depends(require_admin_token),
    service: RunService = Depends(get_run_service),
) -> RunListResponse:
    return RunListResponse(runs=service.list_runs(campaign_id))


@app.post("/campaigns/{campaign_id}/step", response_model=StepCampaignResponse)
def step_campaign(
    campaign_id: UUID,
    request: StepCampaignRequest,
    _: str = Depends(require_admin_token),
    service: CampaignService = Depends(get_campaign_service),
    queue: CampaignQueue = Depends(get_queue),
) -> StepCampaignResponse:
    settings = get_settings()
    if settings.app.execution_mode == "async" and not request.execute_inline:
        queue.enqueue(CampaignEvent(campaign_id=campaign_id, event_type="step_campaign"))
        return StepCampaignResponse(campaign_id=campaign_id, status="queued", run_ids=[])
    outcome = service.step_campaign(campaign_id)
    return StepCampaignResponse(
        campaign_id=campaign_id,
        status=outcome["status"],
        run_ids=[UUID(run_id) for run_id in outcome["run_ids"]],
    )


@app.get("/runs/{run_id}")
def get_run(
    run_id: UUID,
    _: str = Depends(require_admin_token),
    service: RunService = Depends(get_run_service),
) -> SimulationRun:
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return run


@app.get("/artifacts/{artifact_id}")
def get_artifact(
    artifact_id: UUID,
    _: str = Depends(require_admin_token),
    service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactRecord:
    artifact = service.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")
    return artifact


def serve() -> None:
    settings = get_settings()
    uvicorn.run(
        "autolab.api.main:app", host=settings.app.api_host, port=settings.app.api_port, reload=False
    )
