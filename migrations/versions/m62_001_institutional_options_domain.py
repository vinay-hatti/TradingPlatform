"""Milestone 62 canonical Institutional Options opportunity domain.

Revision ID: m62_001
Revises: m61_010
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m62_001"
down_revision = "m61_010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "institutional_option_opportunities",
        sa.Column("opportunity_id", sa.String(128), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("asset_class", sa.String(16), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("conviction", sa.String(32), nullable=False),
        sa.Column("thesis_id", sa.String(128), nullable=False),
        sa.Column("stock_publication_name", sa.String(128), nullable=False),
        sa.Column("stock_scanner_run_id", sa.String(128), nullable=False),
        sa.Column("stock_candidate_id", sa.String(128), nullable=False),
        sa.Column("stock_state_hash", sa.String(128), nullable=False),
        sa.Column("option_snapshot_id", sa.String(128), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("stock_scanner_run_id", "stock_candidate_id", name="uq_m62_stock_candidate_lineage"),
    )
    for name, cols in {
        "ix_m62_opportunities_symbol": ["symbol"],
        "ix_m62_opportunities_state": ["state"],
        "ix_m62_opportunities_direction": ["direction"],
        "ix_m62_opportunities_category": ["category"],
        "ix_m62_opportunities_thesis": ["thesis_id"],
        "ix_m62_opportunities_stock_publication": ["stock_publication_name"],
        "ix_m62_opportunities_stock_run": ["stock_scanner_run_id"],
        "ix_m62_opportunities_stock_candidate": ["stock_candidate_id"],
        "ix_m62_opportunities_stock_hash": ["stock_state_hash"],
        "ix_m62_opportunities_option_snapshot": ["option_snapshot_id"],
        "ix_m62_opportunities_created": ["created_at"],
    }.items():
        op.create_index(name, "institutional_option_opportunities", cols)

    op.create_table(
        "institutional_option_theses",
        sa.Column("thesis_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False, unique=True),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("setup_category", sa.String(64), nullable=False),
        sa.Column("primary_timeframe", sa.String(16), nullable=False),
        sa.Column("invalidation_level", sa.Float(), nullable=False),
        sa.Column("entry_zone_low", sa.Float(), nullable=False),
        sa.Column("entry_zone_high", sa.Float(), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_m62_theses_opportunity", "institutional_option_theses", ["opportunity_id"])
    op.create_index("ix_m62_theses_direction", "institutional_option_theses", ["direction"])
    op.create_index("ix_m62_theses_category", "institutional_option_theses", ["setup_category"])

    op.create_table(
        "institutional_option_strategy_candidates",
        sa.Column("strategy_candidate_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False),
        sa.Column("strategy", sa.String(64), nullable=False),
        sa.Column("disposition", sa.String(32), nullable=False),
        sa.Column("eligibility_score", sa.Float(), nullable=False),
        sa.Column("strategy_score", sa.Float(), nullable=True),
        sa.Column("complexity", sa.String(32), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("opportunity_id", "strategy", name="uq_m62_opportunity_strategy"),
    )
    op.create_index("ix_m62_strategy_opportunity", "institutional_option_strategy_candidates", ["opportunity_id"])
    op.create_index("ix_m62_strategy_name", "institutional_option_strategy_candidates", ["strategy"])
    op.create_index("ix_m62_strategy_disposition", "institutional_option_strategy_candidates", ["disposition"])

    op.create_table(
        "institutional_option_strategy_comparisons",
        sa.Column("comparison_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False, unique=True),
        sa.Column("selected_strategy_candidate_id", sa.String(128), nullable=True),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_m62_comparison_opportunity", "institutional_option_strategy_comparisons", ["opportunity_id"])
    op.create_index("ix_m62_comparison_selected", "institutional_option_strategy_comparisons", ["selected_strategy_candidate_id"])

    op.create_table(
        "institutional_option_contract_recommendations",
        sa.Column("contract_recommendation_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False),
        sa.Column("strategy_candidate_id", sa.String(128), nullable=False),
        sa.Column("option_snapshot_id", sa.String(128), nullable=False),
        sa.Column("executable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("liquidity_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_m62_contract_opportunity", "institutional_option_contract_recommendations", ["opportunity_id"])
    op.create_index("ix_m62_contract_strategy", "institutional_option_contract_recommendations", ["strategy_candidate_id"])
    op.create_index("ix_m62_contract_snapshot", "institutional_option_contract_recommendations", ["option_snapshot_id"])

    op.create_table(
        "institutional_option_execution_recommendations",
        sa.Column("execution_recommendation_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False, unique=True),
        sa.Column("strategy_candidate_id", sa.String(128), nullable=False),
        sa.Column("contract_recommendation_id", sa.String(128), nullable=False),
        sa.Column("underlying_stop", sa.Float(), nullable=False),
        sa.Column("trailing_policy", sa.String(64), nullable=False),
        sa.Column("ready_for_trade_builder", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_m62_execution_opportunity", "institutional_option_execution_recommendations", ["opportunity_id"])
    op.create_index("ix_m62_execution_strategy", "institutional_option_execution_recommendations", ["strategy_candidate_id"])
    op.create_index("ix_m62_execution_contract", "institutional_option_execution_recommendations", ["contract_recommendation_id"])

    op.create_table(
        "institutional_option_outcome_attributions",
        sa.Column("attribution_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False, unique=True),
        sa.Column("strategy_candidate_id", sa.String(128), nullable=True),
        sa.Column("contract_recommendation_id", sa.String(128), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column("realized_return_pct", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(64), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_m62_outcome_opportunity", "institutional_option_outcome_attributions", ["opportunity_id"])
    op.create_index("ix_m62_outcome_strategy", "institutional_option_outcome_attributions", ["strategy_candidate_id"])
    op.create_index("ix_m62_outcome_contract", "institutional_option_outcome_attributions", ["contract_recommendation_id"])
    op.create_index("ix_m62_outcome_status", "institutional_option_outcome_attributions", ["outcome"])
    op.create_index("ix_m62_outcome_exit_reason", "institutional_option_outcome_attributions", ["exit_reason"])

    op.create_table(
        "institutional_option_opportunity_audit",
        sa.Column("audit_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False),
        sa.Column("previous_state", sa.String(32), nullable=True),
        sa.Column("new_state", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("event_timestamp", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_m62_audit_opportunity", "institutional_option_opportunity_audit", ["opportunity_id"])
    op.create_index("ix_m62_audit_state", "institutional_option_opportunity_audit", ["new_state"])
    op.create_index("ix_m62_audit_timestamp", "institutional_option_opportunity_audit", ["event_timestamp"])


def downgrade():
    for table in (
        "institutional_option_opportunity_audit",
        "institutional_option_outcome_attributions",
        "institutional_option_execution_recommendations",
        "institutional_option_contract_recommendations",
        "institutional_option_strategy_comparisons",
        "institutional_option_strategy_candidates",
        "institutional_option_theses",
        "institutional_option_opportunities",
    ):
        op.drop_table(table)
