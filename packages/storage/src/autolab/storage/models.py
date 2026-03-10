from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql.type_api import TypeEngine


def json_type() -> TypeEngine[Any]:
    return JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class CampaignORM(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(64))
    simulator: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64))
    seed: Mapped[int] = mapped_column(Integer)
    budget_max_runs: Mapped[int] = mapped_column(Integer)
    budget_batch_size: Mapped[int] = mapped_column(Integer)
    budget_max_failures: Mapped[int] = mapped_column(Integer)
    tags: Mapped[list[str]] = mapped_column(json_type(), default=list)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column("metadata", json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    objectives: Mapped[list[ObjectiveORM]] = relationship(cascade="all, delete-orphan")
    constraints: Mapped[list[ConstraintORM]] = relationship(cascade="all, delete-orphan")
    search_dimensions: Mapped[list[SearchDimensionORM]] = relationship(cascade="all, delete-orphan")
    candidates: Mapped[list[CandidateORM]] = relationship(cascade="all, delete-orphan")
    runs: Mapped[list[SimulationRunORM]] = relationship(cascade="all, delete-orphan")


class ObjectiveORM(Base):
    __tablename__ = "objectives"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    metric_key: Mapped[str] = mapped_column(String(255))
    direction: Mapped[str] = mapped_column(String(32))
    weight: Mapped[float] = mapped_column(Float)


class ConstraintORM(Base):
    __tablename__ = "constraints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    metric_key: Mapped[str] = mapped_column(String(255))
    operator: Mapped[str] = mapped_column(String(32))
    threshold: Mapped[float] = mapped_column(Float)


class SearchDimensionORM(Base):
    __tablename__ = "search_dimensions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32))
    lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    choices: Mapped[list[str]] = mapped_column(json_type(), default=list)


class CandidateORM(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    batch_index: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(128), default="optimizer")
    values_payload: Mapped[dict[str, Any]] = mapped_column("values", json_type(), default=dict)
    predicted_metrics: Mapped[dict[str, float]] = mapped_column(json_type(), default=dict)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column("metadata", json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class SimulationRunORM(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    simulator: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    failure_class: Mapped[str] = mapped_column(String(32))
    job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column("metadata", json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    metrics: Mapped[list[RunMetricORM]] = relationship(cascade="all, delete-orphan")


class RunMetricORM(Base):
    __tablename__ = "run_metrics"
    __table_args__ = (UniqueConstraint("run_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    value: Mapped[float] = mapped_column(Float)


class ArtifactORM(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=True
    )
    artifact_type: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(128))
    sha256: Mapped[str] = mapped_column(String(64))
    metadata_payload: Mapped[dict[str, Any]] = mapped_column("metadata", json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AgentDecisionORM(Base):
    __tablename__ = "agent_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128))
    rationale: Mapped[str] = mapped_column(Text)
    structured_output: Mapped[dict[str, Any]] = mapped_column(json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class OptimizerStateORM(Base):
    __tablename__ = "optimizer_states"

    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    algorithm: Mapped[str] = mapped_column(String(128))
    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(json_type(), default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class SummaryORM(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=True
    )
    summary_type: Mapped[str] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class SimulatorProvenanceORM(Base):
    __tablename__ = "simulator_provenance"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"))
    simulator: Mapped[str] = mapped_column(String(64))
    adapter_version: Mapped[str] = mapped_column(String(64))
    input_sha256: Mapped[str] = mapped_column(String(64))
    output_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ConfigSnapshotORM(Base):
    __tablename__ = "config_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
