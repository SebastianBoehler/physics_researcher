"""initial schema"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("simulator", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("budget_max_runs", sa.Integer(), nullable=False),
        sa.Column("budget_batch_size", sa.Integer(), nullable=False),
        sa.Column("budget_max_failures", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("workflow", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "objectives",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("metric_key", sa.String(length=255), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
    )
    op.create_table(
        "constraints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("metric_key", sa.String(length=255), nullable=False),
        sa.Column("operator", sa.String(length=32), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
    )
    op.create_table(
        "search_dimensions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("lower", sa.Float(), nullable=True),
        sa.Column("upper", sa.Float(), nullable=True),
        sa.Column("choices", sa.JSON(), nullable=False),
    )
    op.create_table(
        "candidates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False
        ),
        sa.Column("batch_index", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("predicted_metrics", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False
        ),
        sa.Column(
            "candidate_id", sa.String(length=36), sa.ForeignKey("candidates.id"), nullable=False
        ),
        sa.Column("simulator", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_class", sa.String(length=32), nullable=False),
        sa.Column("job_id", sa.String(length=255), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "run_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("simulation_runs.id"), nullable=False
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.UniqueConstraint("run_id", "name"),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False
        ),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("simulation_runs.id"), nullable=True
        ),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "stage_executions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("experiment_id", sa.String(length=36), nullable=False),
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False
        ),
        sa.Column(
            "candidate_id", sa.String(length=36), sa.ForeignKey("candidates.id"), nullable=False
        ),
        sa.Column("simulator", sa.String(length=64), nullable=False),
        sa.Column("stage_name", sa.String(length=128), nullable=False),
        sa.Column("workdir_path", sa.Text(), nullable=False),
        sa.Column("command", sa.JSON(), nullable=False),
        sa.Column("environment", sa.JSON(), nullable=False),
        sa.Column("input_files", sa.JSON(), nullable=False),
        sa.Column("output_files", sa.JSON(), nullable=False),
        sa.Column("log_files", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("simulator_version", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_table(
        "agent_decisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False
        ),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("simulation_runs.id"), nullable=True
        ),
        sa.Column("agent_name", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("structured_output", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "optimizer_states",
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), primary_key=True
        ),
        sa.Column("algorithm", sa.String(length=128), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "summaries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False
        ),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("simulation_runs.id"), nullable=True
        ),
        sa.Column("summary_type", sa.String(length=64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "simulator_provenance",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("simulation_runs.id"), nullable=False
        ),
        sa.Column("simulator", sa.String(length=64), nullable=False),
        sa.Column("adapter_version", sa.String(length=64), nullable=False),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("output_sha256", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "config_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False
        ),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in [
        "config_snapshots",
        "simulator_provenance",
        "summaries",
        "optimizer_states",
        "agent_decisions",
        "artifacts",
        "stage_executions",
        "run_metrics",
        "simulation_runs",
        "candidates",
        "search_dimensions",
        "constraints",
        "objectives",
        "campaigns",
    ]:
        op.drop_table(table)
