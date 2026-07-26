"""Milestone 45 market overview snapshots.
Revision ID: m45_001
Revises: m44_002
"""
from alembic import op
import sqlalchemy as sa
revision='m45_001'; down_revision='m44_002'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('market_overview_snapshot',
      sa.Column('snapshot_timestamp',sa.DateTime(timezone=True),primary_key=True),sa.Column('as_of_date',sa.Date(),nullable=False,index=True),
      sa.Column('market_bias',sa.String(32),nullable=False),sa.Column('preferred_strategy',sa.String(64),nullable=False),
      *[sa.Column(n,sa.Float(),nullable=False) for n in ['market_health_score','trend_score','momentum_score','breadth_score','risk_on_score','sentiment_score','confidence_score']],
      sa.Column('trend_regime',sa.String(32),nullable=False),sa.Column('volatility_regime',sa.String(32),nullable=False),sa.Column('breadth_regime',sa.String(32),nullable=False),sa.Column('liquidity_regime',sa.String(32),nullable=False),sa.Column('correlation_regime',sa.String(32),nullable=False),sa.Column('regime_transition_risk',sa.String(16),nullable=False),sa.Column('payload_json',sa.Text(),nullable=False))
    op.create_table('market_breadth_snapshot',
      sa.Column('snapshot_timestamp',sa.DateTime(timezone=True),primary_key=True),sa.Column('universe_name',sa.String(64),primary_key=True),sa.Column('as_of_date',sa.Date(),nullable=False,index=True),
      *[sa.Column(n,sa.Integer(),nullable=False) for n in ['evaluated_symbols','advancers','decliners','unchanged']],
      *[sa.Column(n,sa.Float(),nullable=False) for n in ['pct_above_ema20','pct_above_sma50','pct_above_sma200']],
      sa.Column('new_highs_20d',sa.Integer(),nullable=False),sa.Column('new_lows_20d',sa.Integer(),nullable=False),sa.Column('up_volume',sa.Float(),nullable=False),sa.Column('down_volume',sa.Float(),nullable=False),sa.Column('breadth_score',sa.Float(),nullable=False),sa.Column('breadth_regime',sa.String(32),nullable=False),sa.Column('payload_json',sa.Text(),nullable=False))
    op.create_table('sector_rotation_snapshot',
      sa.Column('snapshot_timestamp',sa.DateTime(timezone=True),primary_key=True),sa.Column('sector_etf',sa.String(16),primary_key=True),sa.Column('as_of_date',sa.Date(),nullable=False,index=True),sa.Column('sector',sa.String(64),nullable=False),
      *[sa.Column(n,sa.Float(),nullable=False) for n in ['return_1d','return_5d','return_20d','relative_strength','trend_score','momentum_score']],
      sa.Column('dealer_positioning_score',sa.Float()),sa.Column('rotation_label',sa.String(24),nullable=False),sa.Column('payload_json',sa.Text(),nullable=False))

def downgrade():
    op.drop_table('sector_rotation_snapshot'); op.drop_table('market_breadth_snapshot'); op.drop_table('market_overview_snapshot')
