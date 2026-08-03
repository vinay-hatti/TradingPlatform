"""Milestone 55 institutional intelligence snapshots."""
from alembic import op
import sqlalchemy as sa
revision='m55_iif_20260730';down_revision='m54_001';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('institutional_intelligence_snapshots',sa.Column('intelligence_id',sa.String(128),primary_key=True),sa.Column('opportunity_id',sa.String(128),nullable=False),sa.Column('opportunity_version',sa.Integer(),nullable=False),sa.Column('snapshot_id',sa.String(128),nullable=False),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('analytics_version',sa.String(32),nullable=False),sa.Column('generated_at',sa.String(64),nullable=False),sa.Column('generated_by',sa.String(128),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.UniqueConstraint('opportunity_id','opportunity_version','analytics_version',name='uq_intelligence_opportunity_version'))
 for c in ('opportunity_id','snapshot_id','snapshot_timestamp','generated_at'):op.create_index(f'ix_institutional_intelligence_snapshots_{c}','institutional_intelligence_snapshots',[c])
def downgrade():op.drop_table('institutional_intelligence_snapshots')
