"""trend intelligence snapshots
Revision ID: m52_001
Revises: m50_002
"""
from alembic import op
import sqlalchemy as sa
revision='m52_001'; down_revision='m50_002'; branch_labels=None; depends_on=None

def upgrade():
 op.create_table('stock_trend_snapshot',
  sa.Column('snapshot_timestamp',sa.DateTime(timezone=True),nullable=False),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('as_of_date',sa.Date(),nullable=False),
  sa.Column('short_term_state',sa.String(40),nullable=False),sa.Column('intermediate_term_state',sa.String(40),nullable=False),sa.Column('long_term_state',sa.String(40),nullable=False),
  sa.Column('alignment_score',sa.Float(),nullable=False),sa.Column('trend_quality_score',sa.Float(),nullable=False),sa.Column('trend_confidence',sa.Float(),nullable=False),
  sa.Column('trend_stage',sa.String(40),nullable=False),sa.Column('trend_age_days',sa.Integer(),nullable=False),sa.Column('relative_strength_vs_spy',sa.Float(),nullable=False),
  sa.Column('relative_strength_vs_sector',sa.Float(),nullable=False),sa.Column('sector',sa.String(100),nullable=False),sa.Column('sector_etf',sa.String(20),nullable=False),
  sa.Column('calculation_version',sa.String(40),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
  sa.PrimaryKeyConstraint('snapshot_timestamp','symbol'))
 op.create_index('ix_stock_trend_snapshot_symbol_asof','stock_trend_snapshot',['symbol','as_of_date'])
def downgrade():op.drop_table('stock_trend_snapshot')
