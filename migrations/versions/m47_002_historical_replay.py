"""Milestone 47 Phase 7 historical replay audit tables.

Revision ID: m47_002
Revises: m47_001
"""
from alembic import op
import sqlalchemy as sa

revision = "m47_002"
down_revision = "m47_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_replay_run",
        sa.Column("replay_run_id", sa.String(96), primary_key=True),
        sa.Column("replay_mode", sa.String(24), nullable=False),
        sa.Column("source_scanner_run_id", sa.String(96), nullable=True),
        sa.Column("source_decision_run_id", sa.String(96), nullable=True),
        sa.Column("publication_name", sa.String(128), nullable=True),
        sa.Column("ingestion_run_id", sa.String(128), nullable=True),
        sa.Column("option_snapshot_id", sa.String(160), nullable=True),
        sa.Column("market_state_hash", sa.String(64), nullable=True),
        sa.Column("scanner_version", sa.String(64), nullable=True),
        sa.Column("decision_engine_version", sa.String(64), nullable=True),
        sa.Column("policy_version", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decision_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mismatch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_historical_replay_source_scanner", "historical_replay_run", ["source_scanner_run_id"])
    op.create_index("ix_historical_replay_source_decision", "historical_replay_run", ["source_decision_run_id"])
    op.create_index("ix_historical_replay_ingestion", "historical_replay_run", ["ingestion_run_id"])
    op.create_table(
        "historical_replay_comparison",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("replay_run_id", sa.String(96), sa.ForeignKey("historical_replay_run.replay_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("comparison_key", sa.String(512), nullable=False),
        sa.Column("comparison_status", sa.String(24), nullable=False),
        sa.Column("baseline_hash", sa.String(64), nullable=True),
        sa.Column("replay_hash", sa.String(64), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_historical_replay_comparison_run", "historical_replay_comparison", ["replay_run_id"])


def downgrade() -> None:
    op.drop_index("ix_historical_replay_comparison_run", table_name="historical_replay_comparison")
    op.drop_table("historical_replay_comparison")
    op.drop_index("ix_historical_replay_ingestion", table_name="historical_replay_run")
    op.drop_index("ix_historical_replay_source_decision", table_name="historical_replay_run")
    op.drop_index("ix_historical_replay_source_scanner", table_name="historical_replay_run")
    op.drop_table("historical_replay_run")
