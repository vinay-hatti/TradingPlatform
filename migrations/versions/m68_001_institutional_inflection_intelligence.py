"""Milestone 68 institutional inflection intelligence.

Revision ID: m68_001
Revises: m67_001
"""
from alembic import op
import sqlalchemy as sa

revision = "m68_001"
down_revision = "m67_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "institutional_inflection_snapshots",
        sa.Column("snapshot_id", sa.String(128), primary_key=True),
        sa.Column("publication_name", sa.String(128), nullable=False),
        sa.Column("source_run_id", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("transition_state", sa.String(64), nullable=False),
        sa.Column("inflection_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("horizon_min_sessions", sa.Integer(), nullable=False),
        sa.Column("horizon_max_sessions", sa.Integer(), nullable=False),
        sa.Column("state_hash", sa.String(128), nullable=False),
        sa.Column("snapshot_timestamp", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("publication_name", "source_run_id", "symbol", "timeframe", name="uq_m68_inflection_lineage"),
    )
    for name, col in [("ix_m68_inflection_symbol", "symbol"), ("ix_m68_inflection_score", "inflection_score"), ("ix_m68_inflection_run", "source_run_id")]:
        op.create_index(name, "institutional_inflection_snapshots", [col])
    op.create_table(
        "institutional_inflection_timeline_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("transition_state", sa.String(64), nullable=False),
        sa.Column("inflection_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("state_hash", sa.String(128), nullable=False),
        sa.Column("event_timestamp", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("symbol", "timeframe", "state_hash", name="uq_m68_timeline_state"),
    )
    op.create_index("ix_m68_timeline_symbol", "institutional_inflection_timeline_events", ["symbol"])
    op.create_table(
        "institutional_inflection_publications",
        sa.Column("publication_id", sa.String(128), primary_key=True),
        sa.Column("publication_name", sa.String(128), nullable=False, unique=True),
        sa.Column("source_run_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("symbol_count", sa.Integer(), nullable=False),
        sa.Column("high_conviction_count", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("institutional_inflection_publications")
    op.drop_index("ix_m68_timeline_symbol", table_name="institutional_inflection_timeline_events")
    op.drop_table("institutional_inflection_timeline_events")
    for name in ("ix_m68_inflection_run", "ix_m68_inflection_score", "ix_m68_inflection_symbol"):
        op.drop_index(name, table_name="institutional_inflection_snapshots")
    op.drop_table("institutional_inflection_snapshots")
