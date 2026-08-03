"""Milestone 59 institutional execution workspace
Revision ID: 20260803_m59
Revises: 20260730_m58
"""
from alembic import op
import sqlalchemy as sa
revision='20260803_m59';down_revision='20260730_m58';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('execution_intents',sa.Column('execution_intent_id',sa.String(128),primary_key=True),sa.Column('trade_plan_id',sa.String(128),nullable=False),sa.Column('trade_plan_version',sa.Integer,nullable=False),sa.Column('opportunity_id',sa.String(128),nullable=False),sa.Column('portfolio_id',sa.String(64),nullable=False),sa.Column('account_id',sa.String(128),nullable=False),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('strategy',sa.String(64),nullable=False),sa.Column('state',sa.String(32),nullable=False),sa.Column('version',sa.Integer,nullable=False),sa.Column('max_loss',sa.Float,nullable=False),sa.Column('legs_json',sa.JSON,nullable=False),sa.Column('order_request_json',sa.JSON,nullable=False),sa.Column('validation_json',sa.JSON,nullable=False),sa.Column('broker_json',sa.JSON,nullable=False),sa.Column('metadata_json',sa.JSON,nullable=False),sa.Column('created_by',sa.String(128),nullable=False),sa.Column('created_at',sa.String(64),nullable=False),sa.Column('updated_at',sa.String(64),nullable=False),sa.Column('submitted_at',sa.String(64)),sa.Column('terminal_at',sa.String(64)),sa.UniqueConstraint('trade_plan_id','trade_plan_version',name='uq_m59_execution_intent_trade_plan_version'))
 op.create_table('execution_intent_audit_events',sa.Column('event_id',sa.String(128),primary_key=True),sa.Column('execution_intent_id',sa.String(128),nullable=False),sa.Column('execution_intent_version',sa.Integer,nullable=False),sa.Column('event_type',sa.String(64),nullable=False),sa.Column('previous_state',sa.String(32)),sa.Column('new_state',sa.String(32),nullable=False),sa.Column('actor',sa.String(128),nullable=False),sa.Column('reason',sa.Text,nullable=False),sa.Column('event_timestamp',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON,nullable=False),sa.UniqueConstraint('execution_intent_id','execution_intent_version',name='uq_m59_execution_intent_audit_version'))
 for table,cols in {'execution_intents':['trade_plan_id','opportunity_id','portfolio_id','account_id','symbol','strategy','state','created_at'],'execution_intent_audit_events':['execution_intent_id','event_type','new_state','event_timestamp']}.items():
  for col in cols:op.create_index(f'ix_{table}_{col}',table,[col])
def downgrade():
 op.drop_table('execution_intent_audit_events');op.drop_table('execution_intents')
