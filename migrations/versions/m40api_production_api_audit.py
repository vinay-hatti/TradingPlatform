"""Milestone 40 production API audit events.

Revision ID: m40api
Revises: m39pos
"""
from alembic import op
import sqlalchemy as sa

revision = "m40api"
down_revision = "m39pos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_api_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_m40_api_request_id", "production_api_audit_events", ["request_id"])
    op.create_index("ix_m40_api_path", "production_api_audit_events", ["path"])
    op.create_index("ix_m40_api_occurred_at", "production_api_audit_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_m40_api_occurred_at", table_name="production_api_audit_events")
    op.drop_index("ix_m40_api_path", table_name="production_api_audit_events")
    op.drop_index("ix_m40_api_request_id", table_name="production_api_audit_events")
    op.drop_table("production_api_audit_events")
