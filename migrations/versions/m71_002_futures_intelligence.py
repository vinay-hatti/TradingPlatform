"""M71.2 futures intelligence foundation
Revision ID: m71_002
Revises: m71_001
"""
from alembic import op
import sqlalchemy as sa
revision='m71_002';down_revision='m71_001';branch_labels=None;depends_on=None

def upgrade():
    op.create_table('futures_contract_registry',sa.Column('ticker',sa.String(32),primary_key=True),sa.Column('product_code',sa.String(16),nullable=False),sa.Column('as_of_date',sa.String(16),nullable=False),sa.Column('first_trade_date',sa.String(16)),sa.Column('last_trade_date',sa.String(16)),sa.Column('settlement_date',sa.String(16)),sa.Column('days_to_maturity',sa.Integer()),sa.Column('trading_venue',sa.String(16)),sa.Column('active',sa.Integer(),nullable=False,server_default='1'),sa.Column('payload_json',sa.JSON(),nullable=False))
    op.create_index('ix_futures_contract_product','futures_contract_registry',['product_code']);op.create_index('ix_futures_contract_asof','futures_contract_registry',['as_of_date'])
    op.create_table('futures_bars',sa.Column('id',sa.String(128),primary_key=True),sa.Column('product_code',sa.String(16),nullable=False),sa.Column('ticker',sa.String(32),nullable=False),sa.Column('resolution',sa.String(16),nullable=False),sa.Column('window_start_ns',sa.String(32),nullable=False),sa.Column('session_end_date',sa.String(16)),sa.Column('open',sa.Float(),nullable=False),sa.Column('high',sa.Float(),nullable=False),sa.Column('low',sa.Float(),nullable=False),sa.Column('close',sa.Float(),nullable=False),sa.Column('volume',sa.Float(),nullable=False),sa.Column('dollar_volume',sa.Float(),nullable=False),sa.Column('transactions',sa.Integer(),nullable=False),sa.Column('settlement_price',sa.Float()),sa.Column('source',sa.String(32),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.UniqueConstraint('ticker','resolution','window_start_ns',name='uq_m712_futures_bar'))
    for n,c in [('ix_futures_bars_product','product_code'),('ix_futures_bars_ticker','ticker'),('ix_futures_bars_resolution','resolution'),('ix_futures_bars_window','window_start_ns'),('ix_futures_bars_session','session_end_date')]:op.create_index(n,'futures_bars',[c])
    op.create_table('futures_intelligence_snapshots',sa.Column('snapshot_id',sa.String(128),primary_key=True),sa.Column('product_code',sa.String(16),nullable=False),sa.Column('ticker',sa.String(32),nullable=False),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('last_price',sa.Float(),nullable=False),sa.Column('vwap',sa.Float()),sa.Column('overnight_high',sa.Float()),sa.Column('overnight_low',sa.Float()),sa.Column('rth_high',sa.Float()),sa.Column('rth_low',sa.Float()),sa.Column('trend_score',sa.Float(),nullable=False),sa.Column('momentum_score',sa.Float(),nullable=False),sa.Column('realized_volatility',sa.Float(),nullable=False),sa.Column('basis_pct',sa.Float()),sa.Column('confirmation_score',sa.Float(),nullable=False),sa.Column('state',sa.String(32),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False))
    for n,c in [('ix_futures_intel_product','product_code'),('ix_futures_intel_ticker','ticker'),('ix_futures_intel_ts','snapshot_timestamp'),('ix_futures_intel_state','state')]:op.create_index(n,'futures_intelligence_snapshots',[c])

def downgrade():
    op.drop_table('futures_intelligence_snapshots');op.drop_table('futures_bars');op.drop_table('futures_contract_registry')
