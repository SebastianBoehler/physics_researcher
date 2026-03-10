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
    execution_mode: str = "async"

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
    default_simulator: SimulatorKind = SimulatorKind.FAKE
    enable_lammps: bool = False
    enable_openmm: bool = False

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_", extra="ignore")


class ModelProviderConfig(BaseSettings):
    provider: str = "stub"
    model_name: str = "stub-model"
    api_key: str | None = None

    model_config = SettingsConfigDict(env_prefix="AUTOLAB_MODEL_", extra="ignore")


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

    model_config = SettingsConfigDict(
        env_prefix="AUTOLAB_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        self.app.artifact_root.mkdir(parents=True, exist_ok=True)

    def snapshot(self) -> dict[str, object]:
        return self.model_dump(mode="json")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
