"""Milestone 67 live trading governance and certification
Revision ID: m67_001
Revises: m66_001
"""
from alembic import op
import sqlalchemy as sa
revision='m67_001';down_revision='m66_001';branch_labels=None;depends_on=None

def upgrade():
 op.create_table('live_trading_policies',sa.Column('policy_id',sa.String(64),primary_key=True),sa.Column('portfolio_id',sa.String(64),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('status',sa.String(32),nullable=False),sa.Column('environment',sa.String(16),nullable=False),sa.Column('live_routing_enabled',sa.Boolean(),nullable=False),sa.Column('max_trade_loss_pct',sa.Float(),nullable=False),sa.Column('max_daily_loss_pct',sa.Float(),nullable=False),sa.Column('max_portfolio_heat_pct',sa.Float(),nullable=False),sa.Column('max_contracts',sa.Integer(),nullable=False),sa.Column('max_open_orders',sa.Integer(),nullable=False),sa.Column('allowed_symbols_json',sa.JSON(),nullable=False),sa.Column('allowed_strategies_json',sa.JSON(),nullable=False),sa.Column('allowed_order_types_json',sa.JSON(),nullable=False),sa.Column('metadata_json',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('portfolio_id','version',name='uq_m67_policy_version'))
 op.create_index('ix_m67_policy_portfolio','live_trading_policies',['portfolio_id'])
 op.create_table('live_trading_approvals',sa.Column('approval_id',sa.String(64),primary_key=True),sa.Column('portfolio_id',sa.String(64),nullable=False),sa.Column('policy_id',sa.String(64),nullable=False),sa.Column('approval_type',sa.String(32),nullable=False),sa.Column('status',sa.String(32),nullable=False),sa.Column('requested_by',sa.String(128),nullable=False),sa.Column('approved_by',sa.String(128)),sa.Column('reason',sa.String(512),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True)),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
 op.create_index('ix_m67_approval_portfolio','live_trading_approvals',['portfolio_id'])
 op.create_table('live_trading_kill_switches',sa.Column('switch_id',sa.String(64),primary_key=True),sa.Column('portfolio_id',sa.String(64),nullable=False),sa.Column('scope',sa.String(32),nullable=False),sa.Column('scope_value',sa.String(128),nullable=False),sa.Column('active',sa.Boolean(),nullable=False),sa.Column('action',sa.String(32),nullable=False),sa.Column('reason',sa.String(512),nullable=False),sa.Column('activated_by',sa.String(128),nullable=False),sa.Column('activated_at',sa.DateTime(timezone=True),nullable=False),sa.Column('cleared_by',sa.String(128)),sa.Column('cleared_at',sa.DateTime(timezone=True)),sa.Column('metadata_json',sa.JSON(),nullable=False))
 op.create_index('ix_m67_kill_portfolio','live_trading_kill_switches',['portfolio_id'])
 op.create_table('live_trading_certification_runs',sa.Column('run_id',sa.String(64),primary_key=True),sa.Column('portfolio_id',sa.String(64),nullable=False),sa.Column('policy_id',sa.String(64),nullable=False),sa.Column('status',sa.String(32),nullable=False),sa.Column('passed_checks',sa.Integer(),nullable=False),sa.Column('failed_checks',sa.Integer(),nullable=False),sa.Column('checks_json',sa.JSON(),nullable=False),sa.Column('evidence_json',sa.JSON(),nullable=False),sa.Column('started_at',sa.DateTime(timezone=True),nullable=False),sa.Column('completed_at',sa.DateTime(timezone=True)))
 op.create_index('ix_m67_cert_portfolio','live_trading_certification_runs',['portfolio_id'])
 op.create_table('live_trading_audit_events',sa.Column('event_id',sa.String(64),primary_key=True),sa.Column('portfolio_id',sa.String(64),nullable=False),sa.Column('event_type',sa.String(64),nullable=False),sa.Column('actor',sa.String(128),nullable=False),sa.Column('reason',sa.String(512),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
 op.create_index('ix_m67_audit_portfolio','live_trading_audit_events',['portfolio_id'])

def downgrade():
 for t in ['live_trading_audit_events','live_trading_certification_runs','live_trading_kill_switches','live_trading_approvals','live_trading_policies']: op.drop_table(t)
