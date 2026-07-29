"""trend forecasting snapshots
Revision ID: m52_003
Revises: m52_002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="m52_003"; down_revision="m52_002"; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("stock_trend_forecast_snapshot",
        sa.Column("id",sa.BigInteger(),primary_key=True,autoincrement=True),
        sa.Column("symbol",sa.String(32),nullable=False),sa.Column("as_of_date",sa.Date(),nullable=False),
        sa.Column("snapshot_timestamp",sa.DateTime(timezone=True),nullable=False),sa.Column("horizon_days",sa.Integer(),nullable=False),
        sa.Column("status",sa.String(32),nullable=False),sa.Column("payload_json",postgresql.JSONB(astext_type=sa.Text()),nullable=False))
    op.create_index("ix_trend_forecast_symbol_horizon_timestamp","stock_trend_forecast_snapshot",["symbol","horizon_days","snapshot_timestamp"])

def downgrade():
    op.drop_index("ix_trend_forecast_symbol_horizon_timestamp",table_name="stock_trend_forecast_snapshot")
    op.drop_table("stock_trend_forecast_snapshot")
