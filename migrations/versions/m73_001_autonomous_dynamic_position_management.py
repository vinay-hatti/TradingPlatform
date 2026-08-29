
"""M73 autonomous dynamic position management foundation.
Revision ID: m73_001
Revises: m72_001
"""
from alembic import op
import sqlalchemy as sa
revision='m73_001';down_revision='m72_001';branch_labels=None;depends_on=None

def upgrade():
 op.create_table('m73_position_managers',sa.Column('manager_id',sa.String(128),primary_key=True),sa.Column('position_id',sa.String(128),nullable=False,unique=True),sa.Column('portfolio_id',sa.String(128),nullable=False),sa.Column('state',sa.String(40),nullable=False),sa.Column('automation_mode',sa.String(40),nullable=False),sa.Column('protection_state',sa.String(40),nullable=False),sa.Column('heartbeat_at',sa.String(64),nullable=False),sa.Column('activated_at',sa.String(64),nullable=False),sa.Column('recovered_at',sa.String(64)),sa.Column('last_decision',sa.String(40)),sa.Column('conviction_score',sa.Float(),nullable=False),sa.Column('thesis_integrity',sa.Float(),nullable=False),sa.Column('metadata_json',sa.JSON(),nullable=False))
 for n,c in [('ix_m73_mgr_position','position_id'),('ix_m73_mgr_portfolio','portfolio_id'),('ix_m73_mgr_state','state'),('ix_m73_mgr_heartbeat','heartbeat_at')]:op.create_index(n,'m73_position_managers',[c])
 op.create_table('m73_management_decisions',sa.Column('decision_id',sa.String(128),primary_key=True),sa.Column('position_id',sa.String(128),nullable=False),sa.Column('manager_id',sa.String(128),nullable=False),sa.Column('cycle_timestamp',sa.String(64),nullable=False),sa.Column('action',sa.String(40),nullable=False),sa.Column('confidence',sa.Float(),nullable=False),sa.Column('conviction_score',sa.Float(),nullable=False),sa.Column('thesis_integrity',sa.Float(),nullable=False),sa.Column('current_stop',sa.Float()),sa.Column('current_target',sa.Float()),sa.Column('evidence_json',sa.JSON(),nullable=False),sa.Column('explanation',sa.Text(),nullable=False))
 for n,c in [('ix_m73_dec_position','position_id'),('ix_m73_dec_manager','manager_id'),('ix_m73_dec_ts','cycle_timestamp'),('ix_m73_dec_action','action')]:op.create_index(n,'m73_management_decisions',[c])
 op.create_table('m73_exit_reservations',sa.Column('reservation_id',sa.String(128),primary_key=True),sa.Column('position_id',sa.String(128),nullable=False),sa.Column('instruction_id',sa.String(128),nullable=False),sa.Column('status',sa.String(32),nullable=False),sa.Column('reserved_quantity',sa.Integer(),nullable=False),sa.Column('created_at',sa.String(64),nullable=False),sa.Column('updated_at',sa.String(64),nullable=False),sa.Column('metadata_json',sa.JSON(),nullable=False))
 for n,c in [('ix_m73_res_position','position_id'),('ix_m73_res_instruction','instruction_id'),('ix_m73_res_status','status')]:op.create_index(n,'m73_exit_reservations',[c])
 op.create_table('m73_replay_events',sa.Column('event_id',sa.String(128),primary_key=True),sa.Column('position_id',sa.String(128),nullable=False),sa.Column('event_timestamp',sa.String(64),nullable=False),sa.Column('sequence_no',sa.Integer(),nullable=False),sa.Column('event_type',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.UniqueConstraint('position_id','sequence_no',name='uq_m73_replay_position_sequence'))
 for n,c in [('ix_m73_replay_position','position_id'),('ix_m73_replay_ts','event_timestamp'),('ix_m73_replay_type','event_type')]:op.create_index(n,'m73_replay_events',[c])

def downgrade():
 op.drop_table('m73_replay_events');op.drop_table('m73_exit_reservations');op.drop_table('m73_management_decisions');op.drop_table('m73_position_managers')
