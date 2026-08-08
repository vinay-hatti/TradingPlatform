"""Milestone 61 cumulative foundation.
Revision ID: m61_001
Revises: 20260803_m59
"""
from alembic import op
import sqlalchemy as sa
revision="m61_001"
down_revision="20260803_m59"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('stock_scanner_runs',sa.Column('id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('scanner_run_id',sa.String(128),nullable=False),sa.Column('candidate_id',sa.String(128),nullable=True),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('status',sa.String(32),nullable=False),sa.Column('provider',sa.String(32),nullable=False))
    op.create_table('stock_scanner_candidates',sa.Column('id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('scanner_run_id',sa.String(128),nullable=False),sa.Column('candidate_id',sa.String(128),nullable=True),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('category',sa.String(64),nullable=False),sa.Column('score',sa.Float,nullable=False))
    op.create_table('stock_scanner_timeframe_states',sa.Column('id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('scanner_run_id',sa.String(128),nullable=False),sa.Column('candidate_id',sa.String(128),nullable=True),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('timeframe',sa.String(16),nullable=False),sa.Column('direction',sa.String(32),nullable=False),sa.Column('structure',sa.String(32),nullable=False))
    op.create_table('stock_trade_plans',sa.Column('id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('scanner_run_id',sa.String(128),nullable=False),sa.Column('candidate_id',sa.String(128),nullable=True),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('state',sa.String(32),nullable=False))
    op.create_table('stock_scanner_publications',sa.Column('id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('scanner_run_id',sa.String(128),nullable=False),sa.Column('candidate_id',sa.String(128),nullable=True),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('publication_name',sa.String(128),nullable=False),sa.Column('status',sa.String(32),nullable=False))

def downgrade():
    op.drop_table('stock_scanner_publications')
    op.drop_table('stock_trade_plans')
    op.drop_table('stock_scanner_timeframe_states')
    op.drop_table('stock_scanner_candidates')
    op.drop_table('stock_scanner_runs')
