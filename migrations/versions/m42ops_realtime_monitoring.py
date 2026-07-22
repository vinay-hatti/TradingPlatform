"""Milestone 42 realtime monitoring audit tables."""
from alembic import op
import sqlalchemy as sa
revision='m42ops'; down_revision='m40api'; branch_labels=None; depends_on=None
def upgrade():
 op.create_table('realtime_alert_events',sa.Column('alert_id',sa.String(128),primary_key=True),sa.Column('rule_id',sa.String(128),nullable=False),sa.Column('severity',sa.String(32),nullable=False),sa.Column('status',sa.String(32),nullable=False),sa.Column('source',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
def downgrade(): op.drop_table('realtime_alert_events')
