"""Milestone 50 IBKR paper-account foundation.

Revision ID: m50_001
Revises: m49_001
"""
from alembic import op
import sqlalchemy as sa

revision = "m50_001"
down_revision = "m49_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broker_account_bindings",
        sa.Column("binding_id", sa.String(128), primary_key=True),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("broker_name", sa.String(64), nullable=False),
        sa.Column("broker_environment", sa.String(16), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("base_currency", sa.String(8), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("read_only", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("live_trading_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("broker_name", "broker_account_id", name="uq_broker_account_binding"),
    )
    op.create_index("ix_broker_account_bindings_portfolio_id", "broker_account_bindings", ["portfolio_id"])
    op.create_index("ix_broker_account_bindings_broker_name", "broker_account_bindings", ["broker_name"])
    op.create_index("ix_broker_account_bindings_broker_account_id", "broker_account_bindings", ["broker_account_id"])

    op.create_table(
        "broker_account_snapshots",
        sa.Column("snapshot_id", sa.String(128), primary_key=True),
        sa.Column("binding_id", sa.String(128), nullable=False),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.String(64), nullable=False),
        sa.Column("base_currency", sa.String(8), nullable=False),
        sa.Column("net_liquidation", sa.Float(), nullable=False),
        sa.Column("total_cash_value", sa.Float(), nullable=False),
        sa.Column("available_funds", sa.Float(), nullable=False),
        sa.Column("buying_power", sa.Float(), nullable=False),
        sa.Column("excess_liquidity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("raw_json", sa.JSON(), nullable=False),
    )
    for column in ("binding_id", "portfolio_id", "broker_account_id"):
        op.create_index(f"ix_broker_account_snapshots_{column}", "broker_account_snapshots", [column])

    op.create_table(
        "broker_position_snapshots",
        sa.Column("snapshot_position_id", sa.String(160), primary_key=True),
        sa.Column("account_snapshot_id", sa.String(128), nullable=False),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("local_symbol", sa.String(64), nullable=False, server_default=""),
        sa.Column("security_type", sa.String(16), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("average_cost", sa.Float(), nullable=False),
        sa.Column("expiry", sa.String(16), nullable=False, server_default=""),
        sa.Column("strike", sa.Float()),
        sa.Column("right", sa.String(8), nullable=False, server_default=""),
        sa.Column("multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("captured_at", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
    )
    for column in ("account_snapshot_id", "portfolio_id", "broker_account_id", "contract_id", "symbol"):
        op.create_index(f"ix_broker_position_snapshots_{column}", "broker_position_snapshots", [column])

    op.create_table(
        "broker_reconciliation_runs",
        sa.Column("run_id", sa.String(128), primary_key=True),
        sa.Column("binding_id", sa.String(128), nullable=False),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("started_at", sa.String(64), nullable=False),
        sa.Column("completed_at", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("account_match", sa.Boolean(), nullable=False),
        sa.Column("position_difference_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("error_text", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_broker_reconciliation_runs_binding_id", "broker_reconciliation_runs", ["binding_id"])
    op.create_index("ix_broker_reconciliation_runs_portfolio_id", "broker_reconciliation_runs", ["portfolio_id"])


def downgrade() -> None:
    op.drop_table("broker_reconciliation_runs")
    op.drop_table("broker_position_snapshots")
    op.drop_table("broker_account_snapshots")
    op.drop_table("broker_account_bindings")
