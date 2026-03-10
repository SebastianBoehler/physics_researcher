from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import uvicorn
from autolab.agents import (
    LiteratureResearchRequest as AgentLiteratureResearchRequest,
)
from autolab.agents import (
    LiteratureResearchService,
    ReviewRuntimeUnavailableError,
)
from autolab.api.dependencies import (
    get_artifact_service,
    get_campaign_service,
    get_literature_research_service,
    get_queue,
    get_review_service,
    get_run_service,
    require_admin_token,
)
from autolab.api.schemas import (
    CampaignResponse,
    CreateCampaignRequest,
    CreateReviewPostRequest,
    CreateReviewRequest,
    HealthResponse,
    LiteratureResearchRequest,
    LiteratureResearchResponse,
    ResolveReviewRequest,
    ReviewDetailResponse,
    ReviewListResponse,
    ReviewPostListResponse,
    ReviewRoundRequest,
    ReviewRoundResponse,
    RunListResponse,
    StepCampaignRequest,
    StepCampaignResponse,
)
from autolab.campaigns import (
    ArtifactService,
    CampaignEvent,
    CampaignQueue,
    CampaignService,
    ReviewService,
    RunService,
)
from autolab.core.models import (
    ArtifactRecord,
    Campaign,
    ReviewParticipant,
    ReviewPost,
    SimulationRun,
)
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


@app.post("/literature-research", response_model=LiteratureResearchResponse)
def run_literature_research(
    request: LiteratureResearchRequest,
    _: str = Depends(require_admin_token),
    service: LiteratureResearchService = Depends(get_literature_research_service),
) -> LiteratureResearchResponse:
    try:
        result = service.run(
            AgentLiteratureResearchRequest.model_validate(request.model_dump(mode="json"))
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return LiteratureResearchResponse(result=result)


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


@app.post(
    "/campaigns/{campaign_id}/reviews",
    response_model=ReviewDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    campaign_id: UUID,
    request: CreateReviewRequest,
    _: str = Depends(require_admin_token),
    service: ReviewService = Depends(get_review_service),
) -> ReviewDetailResponse:
    try:
        review = service.create_review(
            campaign_id,
            title=request.title,
            objective=request.objective,
            created_by=request.created_by,
            run_id=request.run_id,
            artifact_ids=request.artifact_ids,
            participants=[
                ReviewParticipant(
                    review_id=UUID(int=0),
                    participant_key=participant.participant_key,
                    participant_type=participant.participant_type,
                    role_label=participant.role_label,
                )
                for participant in request.participants
            ],
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ReviewDetailResponse(review=review)


@app.get("/campaigns/{campaign_id}/reviews", response_model=ReviewListResponse)
def list_reviews(
    campaign_id: UUID,
    run_id: UUID | None = None,
    _: str = Depends(require_admin_token),
    service: ReviewService = Depends(get_review_service),
) -> ReviewListResponse:
    return ReviewListResponse(reviews=service.list_reviews(campaign_id, run_id=run_id))


@app.get("/reviews/{review_id}", response_model=ReviewDetailResponse)
def get_review(
    review_id: UUID,
    _: str = Depends(require_admin_token),
    service: ReviewService = Depends(get_review_service),
) -> ReviewDetailResponse:
    review = service.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    return ReviewDetailResponse(review=review)


@app.get("/reviews/{review_id}/posts", response_model=ReviewPostListResponse)
def list_review_posts(
    review_id: UUID,
    _: str = Depends(require_admin_token),
    service: ReviewService = Depends(get_review_service),
) -> ReviewPostListResponse:
    return ReviewPostListResponse(posts=service.list_posts(review_id))


@app.post("/reviews/{review_id}/posts", response_model=ReviewPost)
def create_review_post(
    review_id: UUID,
    request: CreateReviewPostRequest,
    _: str = Depends(require_admin_token),
    service: ReviewService = Depends(get_review_service),
) -> ReviewPost:
    try:
        return service.add_post(
            review_id,
            author_key=request.author_key,
            author_type=request.author_type,
            body=request.body,
            role_label=request.role_label,
            parent_post_id=request.parent_post_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/reviews/{review_id}/rounds", response_model=ReviewRoundResponse)
def create_review_round(
    review_id: UUID,
    request: ReviewRoundRequest,
    _: str = Depends(require_admin_token),
    service: ReviewService = Depends(get_review_service),
    queue: CampaignQueue = Depends(get_queue),
) -> ReviewRoundResponse:
    settings = get_settings()
    try:
        round_record = service.create_round(
            review_id,
            mode=request.mode,
            participant_keys=request.participant_keys or None,
            queued=settings.app.execution_mode == "async" and not request.execute_inline,
        )
        if settings.app.execution_mode == "async" and not request.execute_inline:
            queue.enqueue(
                CampaignEvent(
                    review_id=review_id,
                    review_round_id=round_record.id,
                    event_type="run_review_round",
                )
            )
            return ReviewRoundResponse(round=round_record)
        executed = service.execute_round(review_id, round_record.id)
        return ReviewRoundResponse(round=executed)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewRuntimeUnavailableError as exc:
        detail = {"message": str(exc), "review_id": str(review_id)}
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/reviews/{review_id}/resolve", response_model=ReviewDetailResponse)
def resolve_review(
    review_id: UUID,
    request: ResolveReviewRequest,
    _: str = Depends(require_admin_token),
    service: ReviewService = Depends(get_review_service),
) -> ReviewDetailResponse:
    try:
        service.resolve_review(
            review_id,
            status=request.status,
            resolution_summary=request.resolution_summary,
            resolved_by=request.resolved_by,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    review = service.get_review(review_id)
    assert review is not None
    return ReviewDetailResponse(review=review)


def serve() -> None:
    settings = get_settings()
    uvicorn.run(
        "autolab.api.main:app", host=settings.app.api_host, port=settings.app.api_port, reload=False
    )
