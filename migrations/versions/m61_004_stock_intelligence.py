"""Milestone 61 cumulative foundation.
Revision ID: m61_004
Revises: m61_003
"""
from alembic import op
import sqlalchemy as sa
revision="m61_004"
down_revision="m61_003"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('stock_breakout_snapshots',sa.Column('id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('scanner_run_id',sa.String(128),nullable=False),sa.Column('candidate_id',sa.String(128),nullable=True),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('state',sa.String(32),nullable=False),sa.Column('confirmation',sa.Float,nullable=False))

def downgrade():
    op.drop_table('stock_breakout_snapshots')
