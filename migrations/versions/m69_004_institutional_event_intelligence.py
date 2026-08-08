"""M69.6 institutional event intelligence analytics."""
from alembic import op
import sqlalchemy as sa
revision='m69_004';down_revision='m69_003';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('institutional_event_pricing_snapshots',sa.Column('snapshot_id',sa.String(160),primary_key=True),sa.Column('event_id',sa.String(128),nullable=False),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('implied_move_pct',sa.Float()),sa.Column('historical_move_pct',sa.Float()),sa.Column('forecast_move_pct',sa.Float()),sa.Column('expected_move_pct',sa.Float()),sa.Column('confidence',sa.Float(),nullable=False),sa.Column('classification',sa.String(48),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False));op.create_index('ix_m696_pricing_event','institutional_event_pricing_snapshots',['event_id','snapshot_timestamp'])
 op.create_table('institutional_event_outcomes',sa.Column('outcome_id',sa.String(160),primary_key=True),sa.Column('event_id',sa.String(128),nullable=False),sa.Column('observed_at',sa.String(64),nullable=False),sa.Column('predicted_move_pct',sa.Float()),sa.Column('realized_move_pct',sa.Float()),sa.Column('forecast_error_pct',sa.Float()),sa.Column('payload_json',sa.JSON(),nullable=False));op.create_index('ix_m696_outcome_event','institutional_event_outcomes',['event_id','observed_at'])
def downgrade():
 op.drop_index('ix_m696_outcome_event',table_name='institutional_event_outcomes');op.drop_table('institutional_event_outcomes');op.drop_index('ix_m696_pricing_event',table_name='institutional_event_pricing_snapshots');op.drop_table('institutional_event_pricing_snapshots')
