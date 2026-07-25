"""Milestone 44 institutional market structure snapshots.

Revision ID: m44_001
Revises: 
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
revision="m44_001"
down_revision="67d010f0650d"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("institutional_market_structure_snapshot",
        sa.Column("symbol",sa.String(16),primary_key=True),sa.Column("as_of_date",sa.Date(),primary_key=True),
        sa.Column("option_snapshot_date",sa.Date(),nullable=False),sa.Column("spot",sa.Float(),nullable=False),
        sa.Column("net_gamma_exposure",sa.Float(),nullable=False),sa.Column("net_delta_exposure",sa.Float(),nullable=False),
        sa.Column("net_vanna_exposure",sa.Float(),nullable=False),sa.Column("net_charm_exposure",sa.Float(),nullable=False),
        sa.Column("gamma_regime",sa.String(32),nullable=False),sa.Column("gamma_flip",sa.Float()),sa.Column("call_wall",sa.Float()),sa.Column("put_wall",sa.Float()),
        sa.Column("institutional_positioning_score",sa.Float(),nullable=False),sa.Column("bull_probability",sa.Float(),nullable=False),sa.Column("bear_probability",sa.Float(),nullable=False),
        sa.Column("range_probability",sa.Float(),nullable=False),sa.Column("breakout_probability",sa.Float(),nullable=False),sa.Column("confidence",sa.String(16),nullable=False),sa.Column("payload_json",sa.Text(),nullable=False))
def downgrade(): op.drop_table("institutional_market_structure_snapshot")
