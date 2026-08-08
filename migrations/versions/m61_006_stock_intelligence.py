"""Milestone 61 cumulative foundation.
Revision ID: m61_006
Revises: m61_005
"""
from alembic import op
import sqlalchemy as sa
revision="m61_006"
down_revision="m61_005"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('stock_opportunity_score_snapshots',sa.Column('id',sa.String(128),primary_key=True),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('scanner_run_id',sa.String(128),nullable=False),sa.Column('candidate_id',sa.String(128),nullable=True),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('primary_category',sa.String(64),nullable=False),sa.Column('overall_score',sa.Float,nullable=False),sa.Column('confidence',sa.Float,nullable=False))

def downgrade():
    op.drop_table('stock_opportunity_score_snapshots')
