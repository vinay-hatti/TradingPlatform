"""Milestone 69.6 governed event intelligence automation.
Revision ID: m69_003
Revises: m69_002
"""
from alembic import op
import sqlalchemy as sa

revision='m69_003'; down_revision='m69_002'; branch_labels=None; depends_on=None

COLUMNS=(
 ('source_event_key',sa.String(256)),('release_name',sa.String(256)),('event_time',sa.String(32)),
 ('event_timezone',sa.String(64)),('event_session',sa.String(32)),('event_time_status',sa.String(32)),
 ('calendar_source',sa.String(64)),('date_status',sa.String(32)),('implied_move_pct',sa.Float()),
 ('forecast_move_pct',sa.Float()),('historical_sample_size',sa.Integer()),('calculation_method',sa.String(96)),
 ('options_snapshot_id',sa.String(128)),('event_components_json',sa.JSON()),('evidence_json',sa.JSON()),
 ('source_updated_at',sa.String(64)),('first_seen_at',sa.String(64)),('last_seen_at',sa.String(64)),
 ('superseded_at',sa.String(64)),('revision_number',sa.Integer()),('meeting_start_date',sa.String(32)),
 ('meeting_end_date',sa.String(32)),('content_hash',sa.String(128)),('record_origin',sa.String(32)),
)

def upgrade():
    for name, typ in COLUMNS:
        op.add_column('institutional_option_valuation_events', sa.Column(name,typ,nullable=True))
    op.create_index('ix_m696_event_status_date','institutional_option_valuation_events',['status','event_date'])
    op.create_index('ix_m696_event_symbol_status_date','institutional_option_valuation_events',['symbol','status','event_date'])
    op.create_index('ix_m696_event_source_key','institutional_option_valuation_events',['calendar_source','source_event_key'],unique=True)
    op.create_index('ix_m696_event_type_status_date','institutional_option_valuation_events',['event_type','status','event_date'])

def downgrade():
    for n in ('ix_m696_event_type_status_date','ix_m696_event_source_key','ix_m696_event_symbol_status_date','ix_m696_event_status_date'):
        op.drop_index(n,table_name='institutional_option_valuation_events')
    for name,_ in reversed(COLUMNS):
        op.drop_column('institutional_option_valuation_events',name)
