from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from autolab.core.enums import SimulatorKind
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    env: str = "local"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    artifact_root: Path = Path("artifacts")
    web_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:3000",
            "http://localhost:3000",
            "http://127.0.0.1:4173",
            "http://localhost:4173",
            "http://127.0.0.1:8080",
            "http://localhost:8080",
        ]
    )
    execution_mode: str = "async"
    max_parallel_runs: int = 1
    max_parallel_benchmark_campaigns: int = 1

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_", extra="ignore")


class DatabaseConfig(BaseSettings):
    url: str = "sqlite+pysqlite:///./autolab.db"

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_DATABASE_", extra="ignore")


class RedisConfig(BaseSettings):
    url: str = "redis://localhost:6379/0"
    stream_name: str = "autolab:events"
    group_name: str = "autolab-workers"

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_REDIS_", extra="ignore")


class RayConfig(BaseSettings):
    address: str = "local"

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_RAY_", extra="ignore")


class MlflowConfig(BaseSettings):
    tracking_uri: str = "file:./mlruns"
    experiment_name: str = "autolab"

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_MLFLOW_", extra="ignore")


class OTelConfig(BaseSettings):
    service_name: str = "autolab"
    exporter_otlp_endpoint: str = "http://localhost:4317"

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_OTEL_", extra="ignore")


class AuthConfig(BaseSettings):
    admin_token: str = "dev-token"

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_", extra="ignore")


class SimulatorConfig(BaseSettings):
    default_simulator: SimulatorKind = SimulatorKind.LAMMPS
    enable_lammps: bool = True
    enable_meep: bool = False
    enable_quantum_espresso: bool = False
    enable_openmm: bool = False
    enable_elmer: bool = False
    enable_devsim: bool = False
    working_directory_root: Path = Path("artifacts/runs")
    artifact_retention_policy: str = "keep"
    default_timeout_seconds: int = 900
    lammps_bin: str = "lmp"
    lammps_timeout_seconds: int = 900
    lammps_wrapper: str | None = None
    lammps_environment: dict[str, str] = Field(default_factory=dict)
    meep_bin: str = "python"
    meep_timeout_seconds: int = 900
    meep_wrapper: str | None = None
    meep_environment: dict[str, str] = Field(default_factory=dict)
    qe_pw_bin: str = "pw.x"
    quantum_espresso_timeout_seconds: int = 1800
    quantum_espresso_wrapper: str | None = None
    quantum_espresso_environment: dict[str, str] = Field(default_factory=dict)
    openmm_bin: str = "python"
    openmm_timeout_seconds: int = 900
    openmm_wrapper: str | None = None
    openmm_environment: dict[str, str] = Field(default_factory=dict)
    elmer_solver_bin: str = "ElmerSolver"
    elmer_timeout_seconds: int = 1800
    elmer_wrapper: str | None = None
    elmer_environment: dict[str, str] = Field(default_factory=dict)
    devsim_bin: str = "devsim"
    devsim_timeout_seconds: int = 900
    devsim_wrapper: str | None = None
    devsim_environment: dict[str, str] = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_", extra="ignore")


class ModelProviderConfig(BaseSettings):
    provider: str = "stub"
    model_name: str = "stub-model"
    api_key: str | None = None

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_MODEL_", extra="ignore")


class LiteratureConfig(BaseSettings):
    arxiv_api_url: str = "https://export.arxiv.org/api/query"
    user_agent: str = "autolab-literature/0.1"
    timeout_seconds: float = 15.0
    max_results_per_query: int = 5

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_LITERATURE_", extra="ignore")


class Settings(BaseSettings):
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    ray: RayConfig = Field(default_factory=RayConfig)
    mlflow: MlflowConfig = Field(default_factory=MlflowConfig)
    otel: OTelConfig = Field(default_factory=OTelConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    simulators: SimulatorConfig = Field(default_factory=SimulatorConfig)
    model_provider: ModelProviderConfig = Field(default_factory=ModelProviderConfig)
    literature: LiteratureConfig = Field(default_factory=LiteratureConfig)

    model_config = SettingsConfigDict(
        env_prefix="AUTOLAB_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        self.app.artifact_root.mkdir(parents=True, exist_ok=True)
        self.simulators.working_directory_root.mkdir(parents=True, exist_ok=True)

    def snapshot(self) -> dict[str, object]:
        return self.model_dump(mode="json")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
