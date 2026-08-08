"""Milestone 62 strategy valuation and dynamic management.

Revision ID: m62_002
Revises: m62_001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m62_002"
down_revision = "m62_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "institutional_option_strategy_valuations",
        sa.Column("valuation_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False),
        sa.Column("strategy_candidate_id", sa.String(128), nullable=False),
        sa.Column("strategy_score", sa.Float(), nullable=False),
        sa.Column("calibrated_probability", sa.Float(), nullable=True),
        sa.Column("expected_value", sa.Float(), nullable=True),
        sa.Column("expected_return_on_risk", sa.Float(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("opportunity_id", "strategy_candidate_id", name="uq_m62_strategy_valuation"),
    )
    op.create_index("ix_m62_valuation_opportunity", "institutional_option_strategy_valuations", ["opportunity_id"])
    op.create_index("ix_m62_valuation_strategy", "institutional_option_strategy_valuations", ["strategy_candidate_id"])
    op.create_index("ix_m62_valuation_selected", "institutional_option_strategy_valuations", ["selected"])
    op.create_index("ix_m62_valuation_created", "institutional_option_strategy_valuations", ["created_at"])

    op.create_table(
        "institutional_option_management_snapshots",
        sa.Column("management_snapshot_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False),
        sa.Column("strategy_candidate_id", sa.String(128), nullable=False),
        sa.Column("thesis_integrity", sa.Float(), nullable=False),
        sa.Column("position_health", sa.Float(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("trailing_policy", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_m62_management_opportunity", "institutional_option_management_snapshots", ["opportunity_id"])
    op.create_index("ix_m62_management_strategy", "institutional_option_management_snapshots", ["strategy_candidate_id"])
    op.create_index("ix_m62_management_action", "institutional_option_management_snapshots", ["action"])
    op.create_index("ix_m62_management_created", "institutional_option_management_snapshots", ["created_at"])


def downgrade():
    op.drop_table("institutional_option_management_snapshots")
    op.drop_table("institutional_option_strategy_valuations")
