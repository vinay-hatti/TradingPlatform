"""M71 OPEX intelligence and probabilistic path forecasting.
Revision ID: m71_001
Revises: m70_003
"""
from alembic import op
import sqlalchemy as sa
revision='m71_001';down_revision='m70_003';branch_labels=None;depends_on=None

def upgrade():
    op.create_table('opex_forecast_snapshots',
      sa.Column('forecast_id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(16),nullable=False,index=True),sa.Column('expiration',sa.String(16),nullable=False,index=True),sa.Column('cycle_type',sa.String(24),nullable=False,index=True),sa.Column('dte',sa.Integer(),nullable=False),sa.Column('forecast_timestamp',sa.String(64),nullable=False,index=True),sa.Column('source_as_of_date',sa.String(16),nullable=False,index=True),sa.Column('spot',sa.Float(),nullable=False),sa.Column('range50_low',sa.Float(),nullable=False),sa.Column('range50_high',sa.Float(),nullable=False),sa.Column('range68_low',sa.Float(),nullable=False),sa.Column('range68_high',sa.Float(),nullable=False),sa.Column('range90_low',sa.Float(),nullable=False),sa.Column('range90_high',sa.Float(),nullable=False),sa.Column('magnet',sa.Float()),sa.Column('magnet_probability',sa.Float(),nullable=False),sa.Column('support',sa.Float()),sa.Column('resistance',sa.Float()),sa.Column('gamma_flip_current',sa.Float()),sa.Column('gamma_flip_forecast',sa.Float()),sa.Column('call_wall_current',sa.Float()),sa.Column('call_wall_forecast',sa.Float()),sa.Column('put_wall_current',sa.Float()),sa.Column('put_wall_forecast',sa.Float()),sa.Column('dealer_pressure',sa.Float(),nullable=False),sa.Column('confidence',sa.Float(),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.UniqueConstraint('symbol','expiration','forecast_timestamp',name='uq_m71_opex_symbol_exp_ts'))
    op.create_table('opex_forecast_publications',sa.Column('publication_id',sa.String(128),primary_key=True),sa.Column('publication_name',sa.String(96),nullable=False,unique=True,index=True),sa.Column('status',sa.String(24),nullable=False,index=True),sa.Column('published_at',sa.String(64),nullable=False,index=True),sa.Column('forecast_count',sa.Integer(),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False))
    op.create_table('opex_forecast_outcomes',sa.Column('outcome_id',sa.String(128),primary_key=True),sa.Column('forecast_id',sa.String(128),nullable=False,unique=True,index=True),sa.Column('symbol',sa.String(16),nullable=False,index=True),sa.Column('expiration',sa.String(16),nullable=False,index=True),sa.Column('settlement_price',sa.Float(),nullable=False),sa.Column('in_50',sa.Integer(),nullable=False),sa.Column('in_68',sa.Integer(),nullable=False),sa.Column('in_90',sa.Integer(),nullable=False),sa.Column('magnet_distance_pct',sa.Float()),sa.Column('realized_at',sa.String(64),nullable=False,index=True),sa.Column('payload_json',sa.JSON(),nullable=False))

def downgrade():
    op.drop_table('opex_forecast_outcomes');op.drop_table('opex_forecast_publications');op.drop_table('opex_forecast_snapshots')
