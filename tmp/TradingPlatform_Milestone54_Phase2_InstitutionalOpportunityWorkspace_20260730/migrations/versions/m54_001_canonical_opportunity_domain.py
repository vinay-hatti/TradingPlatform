"""Milestone 54 Phase 1 canonical opportunity domain.

Revision ID: m54_001
Revises: m52_004
"""
from alembic import op
import sqlalchemy as sa

revision = "m54_001"
down_revision = "m52_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("opportunities",
        sa.Column("opportunity_id", sa.String(128), primary_key=True),
        sa.Column("scanner_run_id", sa.String(128), nullable=False),
        sa.Column("snapshot_id", sa.String(128), nullable=False),
        sa.Column("snapshot_timestamp", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("strategy", sa.String(64), nullable=False),
        sa.Column("workflow_state", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("scanner_run_id", "snapshot_id", "symbol", "strategy", name="uq_opportunity_source_identity"),
    )
    for col in ("scanner_run_id", "snapshot_id", "snapshot_timestamp", "symbol", "direction", "strategy", "workflow_state", "created_at"):
        op.create_index(f"ix_opportunities_{col}", "opportunities", [col])
    op.create_table("opportunity_audit_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False),
        sa.Column("opportunity_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("previous_state", sa.String(32)),
        sa.Column("new_state", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("event_timestamp", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("opportunity_id", "opportunity_version", name="uq_opportunity_audit_version"),
    )
    for col in ("opportunity_id", "event_type", "new_state", "event_timestamp"):
        op.create_index(f"ix_opportunity_audit_events_{col}", "opportunity_audit_events", [col])


def downgrade() -> None:
    op.drop_table("opportunity_audit_events")
    op.drop_table("opportunities")
