"""Milestone 61 canonical institutional structure zones.

Revision ID: m61_010
Revises: m61_009
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m61_010"
down_revision = "m61_009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_institutional_structure_zones",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("scanner_run_id", sa.String(128), nullable=False),
        sa.Column("candidate_id", sa.String(128), nullable=True),
        sa.Column("snapshot_timestamp", sa.String(64), nullable=False),
        sa.Column("zone_type", sa.String(32), nullable=False),
        sa.Column("lower_bound", sa.Float(), nullable=False),
        sa.Column("upper_bound", sa.Float(), nullable=False),
        sa.Column("representative_price", sa.Float(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.Column("confluence_score", sa.Float(), nullable=False),
        sa.Column("primary_timeframe", sa.String(16), nullable=False),
        sa.Column("contributing_timeframes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_stock_institutional_structure_zones_symbol", "stock_institutional_structure_zones", ["symbol"])
    op.create_index("ix_stock_institutional_structure_zones_scanner_run_id", "stock_institutional_structure_zones", ["scanner_run_id"])
    op.create_index("ix_stock_institutional_structure_zones_candidate_id", "stock_institutional_structure_zones", ["candidate_id"])
    op.create_index("ix_stock_institutional_structure_zones_snapshot_timestamp", "stock_institutional_structure_zones", ["snapshot_timestamp"])
    op.create_index("ix_stock_institutional_structure_zones_zone_type", "stock_institutional_structure_zones", ["zone_type"])
    op.create_index("ix_stock_institutional_structure_zones_primary_timeframe", "stock_institutional_structure_zones", ["primary_timeframe"])


def downgrade():
    op.drop_table("stock_institutional_structure_zones")
