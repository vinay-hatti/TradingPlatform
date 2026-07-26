"""Milestone 46.4 ingestion publication and scanner readiness.

Revision ID: m46_003
Revises: m46_002
"""
from alembic import op
import sqlalchemy as sa

revision = "m46_003"
down_revision = "m46_002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "market_ingestion_publication",
        sa.Column("publication_name", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(96), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("market_intelligence_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("option_snapshot_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("option_snapshot_id", sa.String(96), nullable=True),
        sa.Column("readiness_status", sa.String(24), nullable=False),
        sa.Column("scanner_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("decision_context_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_market_ingestion_publication_published_at",
        "market_ingestion_publication",
        ["published_at"],
    )


def downgrade():
    op.drop_index("ix_market_ingestion_publication_published_at", table_name="market_ingestion_publication")
    op.drop_table("market_ingestion_publication")
