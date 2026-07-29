"""institutional trend participation snapshots

Revision ID: m52_004
Revises: m52_003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m52_004"
down_revision = "m52_003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_institutional_trend_snapshot",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("snapshot_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("participation_score", sa.Float(), nullable=False),
        sa.Column("leadership_score", sa.Float(), nullable=False),
        sa.Column("trend_quality_score", sa.Float(), nullable=False),
        sa.Column("deterioration_risk_score", sa.Float(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_stock_inst_trend_symbol_timestamp", "stock_institutional_trend_snapshot", ["symbol", "snapshot_timestamp"], unique=False)
    op.create_index("ix_stock_inst_trend_as_of_date", "stock_institutional_trend_snapshot", ["as_of_date"], unique=False)


def downgrade():
    op.drop_index("ix_stock_inst_trend_as_of_date", table_name="stock_institutional_trend_snapshot")
    op.drop_index("ix_stock_inst_trend_symbol_timestamp", table_name="stock_institutional_trend_snapshot")
    op.drop_table("stock_institutional_trend_snapshot")
