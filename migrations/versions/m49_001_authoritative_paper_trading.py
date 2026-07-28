"""Milestone 49 authoritative paper-trading persistence.

Revision ID: m49_001
Revises: m47_002
"""
from alembic import op
import sqlalchemy as sa

revision = "m49_001"
down_revision = "m47_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_orders",
        sa.Column("aggregate_id", sa.String(128), primary_key=True),
        sa.Column("client_order_id", sa.String(128), nullable=False, unique=True),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("order_type", sa.String(32), nullable=False),
        sa.Column("time_in_force", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("total_quantity", sa.Float(), nullable=False),
        sa.Column("filled_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("remaining_quantity", sa.Float(), nullable=False),
        sa.Column("average_fill_price", sa.Float()),
        sa.Column("limit_price", sa.Float()),
        sa.Column("stop_price", sa.Float()),
        sa.Column("outside_regular_hours", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("strategy_name", sa.String(128)),
        sa.Column("broker_order_id", sa.String(128)),
        sa.Column("parent_aggregate_id", sa.String(128)),
        sa.Column("root_aggregate_id", sa.String(128)),
        sa.Column("replace_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("legs_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.Column("terminal_at", sa.String(64)),
        sa.Column("last_event_id", sa.String(128)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    for name, cols in (
        ("ix_canonical_orders_client_order_id", ["client_order_id"]),
        ("ix_canonical_orders_account_id", ["account_id"]),
        ("ix_canonical_orders_idempotency_key", ["idempotency_key"]),
        ("ix_canonical_orders_state", ["state"]),
        ("ix_canonical_orders_broker_order_id", ["broker_order_id"]),
        ("ix_canonical_orders_parent_aggregate_id", ["parent_aggregate_id"]),
        ("ix_canonical_orders_root_aggregate_id", ["root_aggregate_id"]),
    ):
        op.create_index(name, "canonical_orders", cols)

    op.create_table(
        "canonical_order_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.String(128), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("client_order_id", sa.String(128), nullable=False),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("event_timestamp", sa.String(64), nullable=False),
        sa.Column("previous_state", sa.String(32), nullable=False),
        sa.Column("new_state", sa.String(32), nullable=False),
        sa.Column("broker_order_id", sa.String(128)),
        sa.Column("filled_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("remaining_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("average_fill_price", sa.Float()),
        sa.Column("reason", sa.Text()),
        sa.Column("correlation_id", sa.String(128)),
        sa.Column("causation_id", sa.String(128)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("aggregate_id", "aggregate_version", name="uq_canonical_order_event_version"),
    )
    for name, cols in (
        ("ix_canonical_order_events_event_type", ["event_type"]),
        ("ix_canonical_order_events_aggregate_id", ["aggregate_id"]),
        ("ix_canonical_order_events_client_order_id", ["client_order_id"]),
        ("ix_canonical_order_events_account_id", ["account_id"]),
        ("ix_canonical_order_events_event_timestamp", ["event_timestamp"]),
        ("ix_canonical_order_events_correlation_id", ["correlation_id"]),
        ("ix_canonical_order_events_causation_id", ["causation_id"]),
    ):
        op.create_index(name, "canonical_order_events", cols)

    op.create_table(
        "paper_executions",
        sa.Column("execution_key", sa.String(160), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("cycle_id", sa.String(128), nullable=False),
        sa.Column("aggregate_id", sa.String(128), nullable=False),
        sa.Column("client_order_id", sa.String(128), nullable=False),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("order_type", sa.String(32), nullable=False),
        sa.Column("time_in_force", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("requested_quantity", sa.Float(), nullable=False),
        sa.Column("filled_quantity", sa.Float(), nullable=False),
        sa.Column("remaining_quantity", sa.Float(), nullable=False),
        sa.Column("average_fill_price", sa.Float()),
        sa.Column("gross_value", sa.Float(), nullable=False),
        sa.Column("commissions", sa.Float(), nullable=False),
        sa.Column("net_cash_flow", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("rejection_reasons_json", sa.JSON(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    for col in ("session_id", "cycle_id", "aggregate_id", "client_order_id", "account_id", "status"):
        op.create_index(f"ix_paper_executions_{col}", "paper_executions", [col])

    op.create_table(
        "paper_fills",
        sa.Column("fill_id", sa.String(128), primary_key=True),
        sa.Column("execution_key", sa.String(160), nullable=False),
        sa.Column("aggregate_id", sa.String(128), nullable=False),
        sa.Column("client_order_id", sa.String(128), nullable=False),
        sa.Column("leg_id", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("side", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("fill_price", sa.Float(), nullable=False),
        sa.Column("reference_price", sa.Float(), nullable=False),
        sa.Column("slippage_amount", sa.Float(), nullable=False),
        sa.Column("slippage_bps", sa.Float(), nullable=False),
        sa.Column("commission", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("filled_at", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    for col in ("execution_key", "aggregate_id", "client_order_id", "symbol", "filled_at"):
        op.create_index(f"ix_paper_fills_{col}", "paper_fills", [col])

    op.create_table(
        "portfolio_cash_reservations",
        sa.Column("reservation_id", sa.String(128), primary_key=True),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.String(128), nullable=False, unique=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reserved_at", sa.String(64), nullable=False),
        sa.Column("released_at", sa.String(64)),
        sa.Column("release_reason", sa.String(128)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    for col in ("portfolio_id", "aggregate_id", "status"):
        op.create_index(f"ix_portfolio_cash_reservations_{col}", "portfolio_cash_reservations", [col])

    op.create_table(
        "paper_trading_sessions",
        sa.Column("session_id", sa.String(128), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.Column("stopped_at", sa.String(64)),
        sa.Column("profile_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_paper_trading_sessions_account_id", "paper_trading_sessions", ["account_id"])
    op.create_index("ix_paper_trading_sessions_state", "paper_trading_sessions", ["state"])

    op.create_table(
        "paper_automation_checkpoints",
        sa.Column("checkpoint_id", sa.String(128), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("cycle_id", sa.String(128), nullable=False),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.UniqueConstraint("session_id", "cycle_id", "stage", name="uq_paper_checkpoint_stage"),
    )
    for col in ("session_id", "cycle_id", "stage"):
        op.create_index(f"ix_paper_automation_checkpoints_{col}", "paper_automation_checkpoints", [col])

    op.create_table(
        "paper_trading_controls",
        sa.Column("account_id", sa.String(64), primary_key=True),
        sa.Column("entries_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("exits_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("trading_halted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("halt_reason", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )

    op.create_table(
        "paper_position_marks",
        sa.Column("mark_id", sa.String(128), primary_key=True),
        sa.Column("position_id", sa.String(128), nullable=False),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("mark_price", sa.Float(), nullable=False),
        sa.Column("market_value", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("marked_at", sa.String(64), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    for col in ("position_id", "portfolio_id", "marked_at"):
        op.create_index(f"ix_paper_position_marks_{col}", "paper_position_marks", [col])

    op.create_table(
        "paper_position_lifecycle_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("position_id", sa.String(128), nullable=False),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("occurred_at", sa.String(64), nullable=False),
        sa.Column("reference_id", sa.String(128), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    for col in ("position_id", "portfolio_id", "event_type", "occurred_at"):
        op.create_index(f"ix_paper_position_lifecycle_events_{col}", "paper_position_lifecycle_events", [col])


def downgrade() -> None:
    for table in (
        "paper_position_lifecycle_events", "paper_position_marks", "paper_trading_controls",
        "paper_automation_checkpoints", "paper_trading_sessions", "portfolio_cash_reservations",
        "paper_fills", "paper_executions", "canonical_order_events", "canonical_orders",
    ):
        op.drop_table(table)
