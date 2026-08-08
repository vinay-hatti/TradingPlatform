"""Milestone 62 institutional decision snapshots.

Revision ID: m62_005
Revises: m62_004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m62_005"
down_revision = "m62_004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "institutional_option_decision_snapshots",
        sa.Column("decision_snapshot_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False, unique=True),
        sa.Column("strategy_candidate_id", sa.String(128), nullable=False),
        sa.Column("contract_recommendation_id", sa.String(128), nullable=False),
        sa.Column("valuation_id", sa.String(128), nullable=False),
        sa.Column("execution_recommendation_id", sa.String(128), nullable=False),
        sa.Column("management_snapshot_id", sa.String(128), nullable=False),
        sa.Column("institutional_score", sa.Float(), nullable=False),
        sa.Column("calibrated_probability", sa.Float()),
        sa.Column("expected_value", sa.Float()),
        sa.Column("capital_required", sa.Float()),
        sa.Column("selected_strategy", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("state_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    for col in ("opportunity_id", "strategy_candidate_id", "contract_recommendation_id", "valuation_id", "execution_recommendation_id", "management_snapshot_id", "institutional_score", "selected_strategy", "state_hash", "created_at"):
        op.create_index(f"ix_m62_decision_{col}", "institutional_option_decision_snapshots", [col])


def downgrade():
    op.drop_table("institutional_option_decision_snapshots")
