"""Milestone 37 portfolio risk management tables.

Revision ID: m37risk
Revises: m36c0mp
"""
from alembic import op
import sqlalchemy as sa

revision = "m37risk"
down_revision = "m36c0mp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_risk_assessments",
        sa.Column("assessment_id", sa.String(length=128), primary_key=True),
        sa.Column("portfolio_id", sa.String(length=64), nullable=False),
        sa.Column("generated_at", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trading_control", sa.String(length=64), nullable=False),
        sa.Column("net_liquidation_value", sa.Float(), nullable=False),
        sa.Column("cash_balance", sa.Float(), nullable=False),
        sa.Column("capital_committed", sa.Float(), nullable=False),
        sa.Column("open_position_count", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_portfolio_risk_assessments_portfolio_id", "portfolio_risk_assessments", ["portfolio_id"])
    op.create_index("ix_portfolio_risk_assessments_status", "portfolio_risk_assessments", ["status"])
    op.create_table(
        "portfolio_risk_breaches",
        sa.Column("breach_id", sa.String(length=128), primary_key=True),
        sa.Column("assessment_id", sa.String(length=128), nullable=False),
        sa.Column("portfolio_id", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("observed_value", sa.Float(), nullable=False),
        sa.Column("limit_value", sa.Float(), nullable=False),
        sa.Column("recommended_action", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("resolved_at", sa.String(length=64), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
    )
    op.create_index("ix_portfolio_risk_breaches_assessment_id", "portfolio_risk_breaches", ["assessment_id"])
    op.create_index("ix_portfolio_risk_breaches_portfolio_id", "portfolio_risk_breaches", ["portfolio_id"])
    op.create_index("ix_portfolio_risk_breaches_code", "portfolio_risk_breaches", ["code"])
    op.create_index("ix_portfolio_risk_breaches_severity", "portfolio_risk_breaches", ["severity"])
    op.create_index("ix_portfolio_risk_breaches_status", "portfolio_risk_breaches", ["status"])
    op.create_table(
        "portfolio_stress_results",
        sa.Column("result_id", sa.String(length=192), primary_key=True),
        sa.Column("assessment_id", sa.String(length=128), nullable=False),
        sa.Column("portfolio_id", sa.String(length=64), nullable=False),
        sa.Column("scenario_id", sa.String(length=128), nullable=False),
        sa.Column("estimated_pnl", sa.Float(), nullable=False),
        sa.Column("estimated_loss_pct_nav", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_portfolio_stress_results_assessment_id", "portfolio_stress_results", ["assessment_id"])
    op.create_index("ix_portfolio_stress_results_portfolio_id", "portfolio_stress_results", ["portfolio_id"])
    op.create_index("ix_portfolio_stress_results_scenario_id", "portfolio_stress_results", ["scenario_id"])


def downgrade() -> None:
    op.drop_table("portfolio_stress_results")
    op.drop_table("portfolio_risk_breaches")
    op.drop_table("portfolio_risk_assessments")
