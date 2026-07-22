"""Milestone 38 execution orchestration.
Revision ID: m38exec
Revises: m37risk
"""
from alembic import op
import sqlalchemy as sa
revision='m38exec'; down_revision='m37risk'; branch_labels=None; depends_on=None
def upgrade():
    op.create_table('execution_orchestration_orders',sa.Column('execution_order_id',sa.String(128),primary_key=True),sa.Column('client_order_id',sa.String(128),nullable=False),sa.Column('portfolio_id',sa.String(64),nullable=False),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('strategy',sa.String(64),nullable=False),sa.Column('status',sa.String(32),nullable=False),sa.Column('risk_status',sa.String(32),nullable=False),sa.Column('approval_status',sa.String(32),nullable=False),sa.Column('capital_limit',sa.Float(),nullable=False),sa.Column('broker_order_id',sa.String(128)),sa.Column('payload_json',sa.JSON(),nullable=False))
    op.create_index('ix_exec_orders_client_order_id','execution_orchestration_orders',['client_order_id']); op.create_index('ix_exec_orders_portfolio_id','execution_orchestration_orders',['portfolio_id']); op.create_index('ix_exec_orders_symbol','execution_orchestration_orders',['symbol']); op.create_index('ix_exec_orders_status','execution_orchestration_orders',['status'])
    op.create_table('execution_orchestration_events',sa.Column('event_id',sa.String(128),primary_key=True),sa.Column('execution_order_id',sa.String(128),nullable=False),sa.Column('event_type',sa.String(64),nullable=False),sa.Column('from_status',sa.String(32),nullable=False),sa.Column('to_status',sa.String(32),nullable=False),sa.Column('occurred_at',sa.String(64),nullable=False),sa.Column('details_json',sa.JSON(),nullable=False))
    op.create_index('ix_exec_events_order_id','execution_orchestration_events',['execution_order_id']); op.create_index('ix_exec_events_type','execution_orchestration_events',['event_type'])
    op.create_table('execution_orchestration_runs',sa.Column('run_id',sa.String(128),primary_key=True),sa.Column('status',sa.String(32),nullable=False),sa.Column('trading_control',sa.String(64),nullable=False),sa.Column('generated_at',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('notes',sa.Text()))
    op.create_index('ix_exec_runs_status','execution_orchestration_runs',['status'])
def downgrade():
    op.drop_table('execution_orchestration_runs'); op.drop_table('execution_orchestration_events'); op.drop_table('execution_orchestration_orders')
