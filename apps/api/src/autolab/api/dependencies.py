from __future__ import annotations

from functools import lru_cache

from autolab.agents import LiteratureResearchService, PeptideResearchService
from autolab.campaigns import (
    ArtifactService,
    BenchmarkReportService,
    CampaignQueue,
    CampaignService,
    ReviewService,
    RunService,
)
from autolab.core.settings import Settings, get_settings
from autolab.simulators import build_default_registry
from autolab.skills import SkillRegistry, get_builtin_skills
from autolab.storage import init_db
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_campaign_service() -> CampaignService:
    settings = get_settings()
    init_db(settings)
    return CampaignService(settings=settings, simulator_registry=build_default_registry(settings))


def get_run_service(
    campaign_service: CampaignService = Depends(get_campaign_service),
) -> RunService:
    return RunService(campaign_service)


def get_artifact_service(
    campaign_service: CampaignService = Depends(get_campaign_service),
) -> ArtifactService:
    return ArtifactService(campaign_service)


@lru_cache(maxsize=1)
def get_skill_registry() -> SkillRegistry:
    return get_builtin_skills()


@lru_cache(maxsize=1)
def get_benchmark_report_service() -> BenchmarkReportService:
    settings = get_settings()
    settings.ensure_directories()
    return BenchmarkReportService(settings)


@lru_cache(maxsize=1)
def get_review_service() -> ReviewService:
    settings = get_settings()
    init_db(settings)
    return ReviewService(settings=settings)


@lru_cache(maxsize=1)
def get_literature_research_service() -> LiteratureResearchService:
    settings = get_settings()
    return LiteratureResearchService(settings=settings)


@lru_cache(maxsize=1)
def get_peptide_research_service() -> PeptideResearchService:
    settings = get_settings()
    return PeptideResearchService(settings=settings)


def get_queue(settings: Settings = Depends(get_settings)) -> CampaignQueue:
    return CampaignQueue(settings)


def require_admin_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    if credentials is None or credentials.credentials != settings.auth.admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token.",
        )
    return credentials.credentials
