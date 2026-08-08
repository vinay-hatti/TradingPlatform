"""Milestone 64 portfolio-aware decision intelligence

Revision ID: m64_002
Revises: m64_001
"""
from alembic import op
import sqlalchemy as sa
revision='m64_002'; down_revision='m64_001'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('portfolio_correlation_snapshots',
        sa.Column('correlation_snapshot_id',sa.String(128),primary_key=True),
        sa.Column('portfolio_id',sa.String(64),nullable=False),
        sa.Column('risk_snapshot_id',sa.String(128),nullable=False),
        sa.Column('generated_at',sa.String(64),nullable=False),
        sa.Column('payload_json',sa.JSON(),nullable=False))
    op.create_index('ix_m64_corr_portfolio','portfolio_correlation_snapshots',['portfolio_id'])
    op.create_table('portfolio_decision_intelligence_snapshots',
        sa.Column('decision_intelligence_id',sa.String(128),primary_key=True),
        sa.Column('portfolio_id',sa.String(64),nullable=False),
        sa.Column('opportunity_id',sa.String(128),nullable=False),
        sa.Column('institutional_decision_snapshot_id',sa.String(128),nullable=False),
        sa.Column('risk_snapshot_id',sa.String(128),nullable=False),
        sa.Column('portfolio_fit_score',sa.Float(),nullable=False),
        sa.Column('opportunity_cost_score',sa.Float(),nullable=False),
        sa.Column('final_portfolio_score',sa.Float(),nullable=False),
        sa.Column('recommended_quantity',sa.Integer(),nullable=False),
        sa.Column('recommended_capital',sa.Float(),nullable=False),
        sa.Column('decision',sa.String(32),nullable=False),
        sa.Column('rank',sa.Integer()), sa.Column('state_hash',sa.String(128),nullable=False),
        sa.Column('created_at',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),
        sa.UniqueConstraint('portfolio_id','opportunity_id','risk_snapshot_id',name='uq_m64_portfolio_decision_risk'),
        sa.UniqueConstraint('state_hash',name='uq_m64_portfolio_decision_hash'))
    for name,col in [('ix_m64_di_portfolio','portfolio_id'),('ix_m64_di_opportunity','opportunity_id'),('ix_m64_di_rank','rank'),('ix_m64_di_score','final_portfolio_score')]:
        op.create_index(name,'portfolio_decision_intelligence_snapshots',[col])

def downgrade():
    op.drop_table('portfolio_decision_intelligence_snapshots'); op.drop_table('portfolio_correlation_snapshots')
