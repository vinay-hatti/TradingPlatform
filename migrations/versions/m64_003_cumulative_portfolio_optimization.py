"""Milestone 64 cumulative portfolio optimization and action intelligence

Revision ID: m64_003
Revises: m64_002
"""
from alembic import op
import sqlalchemy as sa
revision='m64_003'; down_revision='m64_002'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('portfolio_risk_budget_snapshots',
        sa.Column('budget_snapshot_id',sa.String(128),primary_key=True),
        sa.Column('portfolio_id',sa.String(64),nullable=False),
        sa.Column('risk_snapshot_id',sa.String(128),nullable=False),
        sa.Column('generated_at',sa.String(64),nullable=False),
        sa.Column('status',sa.String(32),nullable=False),
        sa.Column('utilization_pct',sa.Float(),nullable=False),
        sa.Column('payload_json',sa.JSON(),nullable=False),
        sa.UniqueConstraint('portfolio_id','risk_snapshot_id',name='uq_m64_budget_risk'))
    op.create_index('ix_m64_budget_portfolio','portfolio_risk_budget_snapshots',['portfolio_id'])
    op.create_index('ix_m64_budget_risk','portfolio_risk_budget_snapshots',['risk_snapshot_id'])
    op.create_table('portfolio_optimization_snapshots',
        sa.Column('optimization_snapshot_id',sa.String(128),primary_key=True),
        sa.Column('portfolio_id',sa.String(64),nullable=False),
        sa.Column('risk_snapshot_id',sa.String(128),nullable=False),
        sa.Column('generated_at',sa.String(64),nullable=False),
        sa.Column('status',sa.String(32),nullable=False),
        sa.Column('objective_score',sa.Float(),nullable=False),
        sa.Column('selected_count',sa.Integer(),nullable=False),
        sa.Column('recommended_capital',sa.Float(),nullable=False),
        sa.Column('state_hash',sa.String(128),nullable=False),
        sa.Column('payload_json',sa.JSON(),nullable=False),
        sa.UniqueConstraint('portfolio_id','risk_snapshot_id',name='uq_m64_optimizer_risk'),
        sa.UniqueConstraint('state_hash',name='uq_m64_optimizer_hash'))
    op.create_index('ix_m64_optimizer_portfolio','portfolio_optimization_snapshots',['portfolio_id'])
    op.create_index('ix_m64_optimizer_risk','portfolio_optimization_snapshots',['risk_snapshot_id'])
    op.create_table('portfolio_action_recommendations',
        sa.Column('recommendation_id',sa.String(128),primary_key=True),
        sa.Column('portfolio_id',sa.String(64),nullable=False),
        sa.Column('risk_snapshot_id',sa.String(128),nullable=False),
        sa.Column('action_key',sa.String(255),nullable=False),
        sa.Column('action_type',sa.String(32),nullable=False),
        sa.Column('symbol',sa.String(32)),sa.Column('priority',sa.String(24),nullable=False),
        sa.Column('status',sa.String(32),nullable=False),sa.Column('created_at',sa.String(64),nullable=False),
        sa.Column('payload_json',sa.JSON(),nullable=False),
        sa.UniqueConstraint('portfolio_id','risk_snapshot_id','action_key',name='uq_m64_action_risk_key'))
    op.create_index('ix_m64_action_portfolio','portfolio_action_recommendations',['portfolio_id'])
    op.create_index('ix_m64_action_type','portfolio_action_recommendations',['action_type'])
    op.create_table('portfolio_allocation_publications',
        sa.Column('publication_id',sa.String(128),primary_key=True),
        sa.Column('publication_name',sa.String(128),nullable=False),
        sa.Column('portfolio_id',sa.String(64),nullable=False),
        sa.Column('risk_snapshot_id',sa.String(128),nullable=False),
        sa.Column('optimization_snapshot_id',sa.String(128),nullable=False),
        sa.Column('published_at',sa.String(64),nullable=False),
        sa.Column('status',sa.String(32),nullable=False),
        sa.Column('payload_json',sa.JSON(),nullable=False),
        sa.UniqueConstraint('portfolio_id','publication_name',name='uq_m64_portfolio_publication'))
    op.create_index('ix_m64_publication_portfolio','portfolio_allocation_publications',['portfolio_id'])

def downgrade():
    op.drop_table('portfolio_allocation_publications')
    op.drop_table('portfolio_action_recommendations')
    op.drop_table('portfolio_optimization_snapshots')
    op.drop_table('portfolio_risk_budget_snapshots')
