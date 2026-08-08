"""Milestone 61 Phase 8 position intelligence.
Revision ID: m61_007
Revises: m61_006
"""
from alembic import op
import sqlalchemy as sa
revision='m61_007';down_revision='m61_006';branch_labels=None;depends_on=None
def upgrade():
    op.create_table('stock_position_intelligence_snapshots',
        sa.Column('id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(32),nullable=False,index=True),sa.Column('scanner_run_id',sa.String(128),nullable=False,index=True),sa.Column('candidate_id',sa.String(128),nullable=True,index=True),sa.Column('snapshot_timestamp',sa.String(64),nullable=False,index=True),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('action',sa.String(32),nullable=False),sa.Column('thesis_integrity',sa.Float,nullable=False),sa.Column('management_quality',sa.Float,nullable=False))
def downgrade():op.drop_table('stock_position_intelligence_snapshots')
