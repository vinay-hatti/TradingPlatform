"""Milestone 63 broker portfolio synchronization foundation.

Revision ID: m63_001
Revises: m62_005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m63_001"
down_revision = "m62_005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "broker_current_positions",
        sa.Column("broker_position_id", sa.String(160), primary_key=True),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("binding_id", sa.String(128), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("account_snapshot_id", sa.String(128), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("local_symbol", sa.String(64), nullable=False, server_default=""),
        sa.Column("security_type", sa.String(16), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("signed_quantity", sa.Float(), nullable=False),
        sa.Column("average_cost", sa.Float(), nullable=False),
        sa.Column("market_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("market_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("expiry", sa.String(16), nullable=False, server_default=""),
        sa.Column("strike", sa.Float()),
        sa.Column("right", sa.String(8), nullable=False, server_default=""),
        sa.Column("multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("provenance", sa.String(32), nullable=False, server_default="BROKER_DISCOVERED"),
        sa.Column("reconciliation_status", sa.String(32), nullable=False, server_default="MATCHED"),
        sa.Column("portfolio_position_id", sa.String(128)),
        sa.Column("managed_position_id", sa.String(128)),
        sa.Column("first_seen_at", sa.String(64), nullable=False),
        sa.Column("last_seen_at", sa.String(64), nullable=False),
        sa.Column("closed_at", sa.String(64)),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("portfolio_id", "broker_account_id", "contract_id", name="uq_m63_current_broker_position"),
    )
    for col in ("portfolio_id", "binding_id", "broker_account_id", "account_snapshot_id", "contract_id", "symbol", "active", "provenance", "reconciliation_status", "portfolio_position_id", "managed_position_id", "last_seen_at"):
        op.create_index(f"ix_m63_current_{col}", "broker_current_positions", [col])

    op.create_table(
        "broker_portfolio_publications",
        sa.Column("publication_id", sa.String(128), primary_key=True),
        sa.Column("publication_name", sa.String(128), nullable=False),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("account_snapshot_id", sa.String(128), nullable=False),
        sa.Column("reconciliation_run_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("position_count", sa.Integer(), nullable=False),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("broker_discovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("drift_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    for col in ("publication_name", "portfolio_id", "broker_account_id", "account_snapshot_id", "reconciliation_run_id", "status", "published_at"):
        op.create_index(f"ix_m63_publication_{col}", "broker_portfolio_publications", [col])

    op.create_table(
        "broker_portfolio_alerts",
        sa.Column("alert_id", sa.String(128), primary_key=True),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("broker_position_id", sa.String(160)),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("resolved_at", sa.String(64)),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    for col in ("portfolio_id", "broker_position_id", "severity", "alert_type", "status", "created_at"):
        op.create_index(f"ix_m63_alert_{col}", "broker_portfolio_alerts", [col])


def downgrade():
    op.drop_table("broker_portfolio_alerts")
    op.drop_table("broker_portfolio_publications")
    op.drop_table("broker_current_positions")
