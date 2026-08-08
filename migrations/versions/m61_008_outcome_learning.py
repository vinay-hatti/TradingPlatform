"""Milestone 61 Phase 11 outcome tracking and learning.
Revision ID: m61_008
Revises: m61_007
"""
from alembic import op
import sqlalchemy as sa
revision='m61_008';down_revision='m61_007';branch_labels=None;depends_on=None

def _common():
    return [
        sa.Column('id',sa.String(128),primary_key=True),
        sa.Column('symbol',sa.String(32),nullable=False,index=True),
        sa.Column('scanner_run_id',sa.String(128),nullable=False,index=True),
        sa.Column('candidate_id',sa.String(128),nullable=True,index=True),
        sa.Column('snapshot_timestamp',sa.String(64),nullable=False,index=True),
        sa.Column('payload_json',sa.JSON(),nullable=False),
    ]

def upgrade():
    op.create_table('stock_outcome_observations',*_common(),
        sa.Column('outcome',sa.String(32),nullable=False,index=True),
        sa.Column('setup_category',sa.String(64),nullable=False,index=True),
        sa.Column('market_regime',sa.String(64),nullable=False,index=True),
        sa.Column('strategy',sa.String(64),nullable=False,index=True),
        sa.Column('prediction_probability',sa.Float,nullable=False),
        sa.Column('realized_return_pct',sa.Float,nullable=False,server_default='0'),
        sa.Column('management_policy',sa.String(64),nullable=False,index=True))
    op.create_table('stock_outcome_attribution_snapshots',*_common(),
        sa.Column('attribution_type',sa.String(64),nullable=False,index=True),
        sa.Column('attribution_key',sa.String(128),nullable=False,index=True),
        sa.Column('observation_count',sa.Integer,nullable=False,server_default='0'))
    op.create_table('stock_probability_calibration_snapshots',*_common(),
        sa.Column('model_family',sa.String(128),nullable=False,index=True),
        sa.Column('model_version',sa.String(128),nullable=False,index=True),
        sa.Column('observation_count',sa.Integer,nullable=False,server_default='0'),
        sa.Column('brier_score',sa.Float,nullable=True),
        sa.Column('expected_calibration_error',sa.Float,nullable=True))
    op.create_table('stock_management_policy_performance',*_common(),
        sa.Column('policy_name',sa.String(128),nullable=False,index=True),
        sa.Column('observation_count',sa.Integer,nullable=False,server_default='0'),
        sa.Column('expectancy_pct',sa.Float,nullable=False,server_default='0'),
        sa.Column('score',sa.Float,nullable=False,server_default='0'))

def downgrade():
    op.drop_table('stock_management_policy_performance')
    op.drop_table('stock_probability_calibration_snapshots')
    op.drop_table('stock_outcome_attribution_snapshots')
    op.drop_table('stock_outcome_observations')
