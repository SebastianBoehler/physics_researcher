"""add review thread schema"""

import sqlalchemy as sa
from alembic import op

revision = "0002_review_threads"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_threads",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False
        ),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("simulation_runs.id"), nullable=True
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("resolution_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "review_participants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "review_id",
            sa.String(length=36),
            sa.ForeignKey("review_threads.id"),
            nullable=False,
        ),
        sa.Column("participant_key", sa.String(length=128), nullable=False),
        sa.Column("participant_type", sa.String(length=32), nullable=False),
        sa.Column("role_label", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("review_id", "participant_key"),
    )
    op.create_table(
        "review_rounds",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "review_id",
            sa.String(length=36),
            sa.ForeignKey("review_threads.id"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("participant_keys", sa.JSON(), nullable=False),
        sa.Column("recommendation", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "review_posts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "review_id",
            sa.String(length=36),
            sa.ForeignKey("review_threads.id"),
            nullable=False,
        ),
        sa.Column(
            "round_id",
            sa.String(length=36),
            sa.ForeignKey("review_rounds.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "parent_post_id",
            sa.String(length=36),
            sa.ForeignKey("review_posts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("author_key", sa.String(length=128), nullable=False),
        sa.Column("author_type", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("structured_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "review_artifact_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "review_id",
            sa.String(length=36),
            sa.ForeignKey("review_threads.id"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id", sa.String(length=36), sa.ForeignKey("artifacts.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("review_id", "artifact_id"),
    )


def downgrade() -> None:
    for table in [
        "review_artifact_links",
        "review_posts",
        "review_rounds",
        "review_participants",
        "review_threads",
    ]:
        op.drop_table(table)
