"""Milestone 61 cumulative foundation.
Revision ID: m61_002
Revises: m61_001
"""
from alembic import op
import sqlalchemy as sa
revision="m61_002"
down_revision="m61_001"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('stock_support_resistance_levels',sa.Column('id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('scanner_run_id',sa.String(128),nullable=False),sa.Column('candidate_id',sa.String(128),nullable=True),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('timeframe',sa.String(16),nullable=False),sa.Column('level_type',sa.String(32),nullable=False),sa.Column('price',sa.Float,nullable=False),sa.Column('strength',sa.Float,nullable=False))
    op.create_table('stock_supply_demand_zones',sa.Column('id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('scanner_run_id',sa.String(128),nullable=False),sa.Column('candidate_id',sa.String(128),nullable=True),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('timeframe',sa.String(16),nullable=False),sa.Column('zone_type',sa.String(32),nullable=False),sa.Column('lower_bound',sa.Float,nullable=False),sa.Column('upper_bound',sa.Float,nullable=False),sa.Column('strength',sa.Float,nullable=False))

def downgrade():
    op.drop_table('stock_supply_demand_zones')
    op.drop_table('stock_support_resistance_levels')
