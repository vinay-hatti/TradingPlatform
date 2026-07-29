"""trend transition intelligence snapshots
Revision ID: m52_002
Revises: m52_001
"""
from alembic import op
import sqlalchemy as sa
revision='m52_002'; down_revision='m52_001'; branch_labels=None; depends_on=None
def upgrade():
 op.create_table('stock_trend_transition_snapshot',sa.Column('snapshot_timestamp',sa.DateTime(timezone=True),nullable=False),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('as_of_date',sa.Date(),nullable=False),sa.Column('transition_state',sa.String(40),nullable=False),sa.Column('transition_direction',sa.String(20),nullable=False),sa.Column('breakout_state',sa.String(40),nullable=False),sa.Column('confirmation_score',sa.Float(),nullable=False),sa.Column('reversal_risk_score',sa.Float(),nullable=False),sa.Column('exhaustion_risk_score',sa.Float(),nullable=False),sa.Column('volatility_state',sa.String(30),nullable=False),sa.Column('calculation_version',sa.String(40),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.PrimaryKeyConstraint('snapshot_timestamp','symbol'))
 op.create_index('ix_stock_trend_transition_symbol_asof','stock_trend_transition_snapshot',['symbol','as_of_date'])
def downgrade(): op.drop_table('stock_trend_transition_snapshot')
