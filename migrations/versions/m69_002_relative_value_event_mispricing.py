"""Milestone 69.4 relative-value and event mispricing completion.
Revision ID: m69_002
Revises: m69_001
"""
from alembic import op
import sqlalchemy as sa
revision='m69_002'; down_revision='m69_001'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('institutional_option_valuation_events',
        sa.Column('event_id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(32),nullable=False),
        sa.Column('event_type',sa.String(48),nullable=False),sa.Column('event_date',sa.String(32),nullable=False),
        sa.Column('status',sa.String(24),nullable=False),sa.Column('expected_move_pct',sa.Float()),
        sa.Column('historical_move_pct',sa.Float()),sa.Column('confidence',sa.Float(),nullable=False),
        sa.Column('source',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False))
    op.create_index('ix_m69_event_symbol_date','institutional_option_valuation_events',['symbol','event_date'])
    op.create_index('ix_m69_event_type','institutional_option_valuation_events',['event_type'])
    op.create_table('institutional_option_relative_value_snapshots',
        sa.Column('relative_value_id',sa.String(128),primary_key=True),sa.Column('valuation_run_id',sa.String(128),nullable=False),
        sa.Column('contract_recommendation_id',sa.String(128),nullable=False),sa.Column('symbol',sa.String(32),nullable=False),
        sa.Column('sector',sa.String(96),nullable=False),sa.Column('peer_group',sa.String(160),nullable=False),
        sa.Column('symbol_iv',sa.Float(),nullable=False),sa.Column('peer_median_iv',sa.Float(),nullable=False),
        sa.Column('divergence_pct',sa.Float(),nullable=False),sa.Column('z_score',sa.Float(),nullable=False),
        sa.Column('relationship_regime',sa.String(32),nullable=False),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),
        sa.Column('payload_json',sa.JSON(),nullable=False))
    op.create_index('ix_m69_rv_run','institutional_option_relative_value_snapshots',['valuation_run_id'])
    op.create_index('ix_m69_rv_contract','institutional_option_relative_value_snapshots',['contract_recommendation_id'])
    op.create_index('ix_m69_rv_sector','institutional_option_relative_value_snapshots',['sector'])

def downgrade():
    for n in ('ix_m69_rv_sector','ix_m69_rv_contract','ix_m69_rv_run'): op.drop_index(n,table_name='institutional_option_relative_value_snapshots')
    op.drop_table('institutional_option_relative_value_snapshots')
    op.drop_index('ix_m69_event_type',table_name='institutional_option_valuation_events')
    op.drop_index('ix_m69_event_symbol_date',table_name='institutional_option_valuation_events')
    op.drop_table('institutional_option_valuation_events')
