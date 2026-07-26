"""Milestone 47 Phase 5 persistent scanner and decision lineage.

Revision ID: m47_001
Revises: m46_003
"""
from alembic import op
import sqlalchemy as sa

revision = "m47_001"
down_revision = "m46_003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scanner_lineage_run",
        sa.Column("scanner_run_id", sa.String(96), primary_key=True),
        sa.Column("publication_name", sa.String(64), nullable=True),
        sa.Column("ingestion_run_id", sa.String(96), nullable=True),
        sa.Column("publication_status", sa.String(24), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("market_as_of_date", sa.Date(), nullable=True),
        sa.Column("market_intelligence_snapshot_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("option_snapshot_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("option_snapshot_id", sa.String(96), nullable=True),
        sa.Column("option_snapshot_completeness_pct", sa.Float(), nullable=True),
        sa.Column("published_state_degraded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("scanner_version", sa.String(48), nullable=False),
        sa.Column("market_state_hash", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_scanner_lineage_run_publication", "scanner_lineage_run", ["publication_name", "published_at"])
    op.create_table(
        "scanner_candidate_lineage",
        sa.Column("candidate_id", sa.String(96), primary_key=True),
        sa.Column("scanner_run_id", sa.String(96), sa.ForeignKey("scanner_lineage_run.scanner_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("signal", sa.String(16), nullable=True),
        sa.Column("strategy", sa.String(96), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("publication_name", sa.String(64), nullable=True),
        sa.Column("ingestion_run_id", sa.String(96), nullable=True),
        sa.Column("market_intelligence_snapshot_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("option_snapshot_id", sa.String(96), nullable=True),
        sa.Column("market_state_hash", sa.String(64), nullable=False),
        sa.Column("scanner_version", sa.String(48), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_scanner_candidate_lineage_run_rank", "scanner_candidate_lineage", ["scanner_run_id", "rank"])
    op.create_index("ix_scanner_candidate_lineage_symbol", "scanner_candidate_lineage", ["symbol"])
    op.create_table(
        "institutional_decision_lineage_run",
        sa.Column("decision_run_id", sa.String(96), primary_key=True),
        sa.Column("publication_name", sa.String(64), nullable=True),
        sa.Column("ingestion_run_id", sa.String(96), nullable=True),
        sa.Column("publication_status", sa.String(24), nullable=False),
        sa.Column("market_intelligence_snapshot_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("option_snapshot_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("option_snapshot_id", sa.String(96), nullable=True),
        sa.Column("published_state_degraded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("decision_engine_version", sa.String(48), nullable=False),
        sa.Column("policy_version", sa.String(48), nullable=False),
        sa.Column("market_state_hash", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("decision_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_decision_lineage_run_publication", "institutional_decision_lineage_run", ["publication_name", "started_at"])
    op.create_table(
        "institutional_decision_lineage",
        sa.Column("decision_id", sa.String(96), primary_key=True),
        sa.Column("decision_run_id", sa.String(96), sa.ForeignKey("institutional_decision_lineage_run.decision_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("scanner_run_id", sa.String(96), nullable=True),
        sa.Column("candidate_id", sa.String(96), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("strategy", sa.String(96), nullable=True),
        sa.Column("action", sa.String(48), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("publication_name", sa.String(64), nullable=True),
        sa.Column("ingestion_run_id", sa.String(96), nullable=True),
        sa.Column("market_intelligence_snapshot_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("option_snapshot_id", sa.String(96), nullable=True),
        sa.Column("market_state_hash", sa.String(64), nullable=False),
        sa.Column("decision_engine_version", sa.String(48), nullable=False),
        sa.Column("policy_version", sa.String(48), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_decision_lineage_run", "institutional_decision_lineage", ["decision_run_id"])
    op.create_index("ix_decision_lineage_candidate", "institutional_decision_lineage", ["candidate_id"])
    op.create_index("ix_decision_lineage_symbol", "institutional_decision_lineage", ["symbol"])


def downgrade():
    op.drop_index("ix_decision_lineage_symbol", table_name="institutional_decision_lineage")
    op.drop_index("ix_decision_lineage_candidate", table_name="institutional_decision_lineage")
    op.drop_index("ix_decision_lineage_run", table_name="institutional_decision_lineage")
    op.drop_table("institutional_decision_lineage")
    op.drop_index("ix_decision_lineage_run_publication", table_name="institutional_decision_lineage_run")
    op.drop_table("institutional_decision_lineage_run")
    op.drop_index("ix_scanner_candidate_lineage_symbol", table_name="scanner_candidate_lineage")
    op.drop_index("ix_scanner_candidate_lineage_run_rank", table_name="scanner_candidate_lineage")
    op.drop_table("scanner_candidate_lineage")
    op.drop_index("ix_scanner_lineage_run_publication", table_name="scanner_lineage_run")
    op.drop_table("scanner_lineage_run")
