"""M73.0.7 governed execution retry and re-arm.

Revision ID: m73_002
Revises: m73_001
"""
from alembic import op
import sqlalchemy as sa

revision = 'm73_002'
down_revision = 'm73_001'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('execution_intents', sa.Column('execution_attempt', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('execution_intents', sa.Column('parent_execution_intent_id', sa.String(length=128), nullable=True))
    op.add_column('execution_intents', sa.Column('retry_reason', sa.Text(), nullable=True))
    op.create_index('ix_execution_intents_execution_attempt','execution_intents',['execution_attempt'],unique=False)
    op.create_index('ix_execution_intents_parent_execution_intent_id','execution_intents',['parent_execution_intent_id'],unique=False)
    op.drop_constraint('uq_m59_execution_intent_trade_plan_version','execution_intents',type_='unique')
    op.create_unique_constraint('uq_m73_execution_intent_trade_plan_attempt','execution_intents',['trade_plan_id','trade_plan_version','execution_attempt'])

def downgrade():
    # Downgrade is only safe when no trade-plan/version has more than one attempt.
    bind=op.get_bind()
    dup=bind.execute(sa.text("SELECT trade_plan_id, trade_plan_version, COUNT(*) AS n FROM execution_intents GROUP BY trade_plan_id, trade_plan_version HAVING COUNT(*) > 1 LIMIT 1")).first()
    if dup:
        raise RuntimeError('Cannot downgrade m73_002 while multiple execution attempts exist for a trade-plan version')
    op.drop_constraint('uq_m73_execution_intent_trade_plan_attempt','execution_intents',type_='unique')
    op.create_unique_constraint('uq_m59_execution_intent_trade_plan_version','execution_intents',['trade_plan_id','trade_plan_version'])
    op.drop_index('ix_execution_intents_parent_execution_intent_id',table_name='execution_intents')
    op.drop_index('ix_execution_intents_execution_attempt',table_name='execution_intents')
    op.drop_column('execution_intents','retry_reason')
    op.drop_column('execution_intents','parent_execution_intent_id')
    op.drop_column('execution_intents','execution_attempt')
