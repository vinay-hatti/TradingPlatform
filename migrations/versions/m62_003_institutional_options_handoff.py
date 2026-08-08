"""Milestone 62 Phase 8 Institutional Options handoff.

Revision ID: m62_003
Revises: m62_002
"""
from alembic import op
import sqlalchemy as sa

revision = "m62_003"
down_revision = "m62_002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "institutional_option_handoffs",
        sa.Column("handoff_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False),
        sa.Column("strategy_candidate_id", sa.String(128), nullable=False),
        sa.Column("contract_recommendation_id", sa.String(128), nullable=False),
        sa.Column("execution_recommendation_id", sa.String(128), nullable=False),
        sa.Column("account_id", sa.String(128), nullable=False),
        sa.Column("trade_plan_id", sa.String(128)),
        sa.Column("execution_intent_id", sa.String(128)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("overrides_json", sa.JSON(), nullable=False),
        sa.Column("lineage_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.UniqueConstraint("opportunity_id", "account_id", "strategy_candidate_id", name="uq_m62_handoff_source"),
    )
    for column in ("opportunity_id", "strategy_candidate_id", "contract_recommendation_id", "execution_recommendation_id", "account_id", "trade_plan_id", "execution_intent_id", "status", "created_at"):
        op.create_index(f"ix_m62_handoff_{column}", "institutional_option_handoffs", [column])


def downgrade():
    op.drop_table("institutional_option_handoffs")
