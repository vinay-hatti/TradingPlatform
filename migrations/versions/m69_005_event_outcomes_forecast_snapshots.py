"""M69.6 historical outcomes and immutable pre-event forecast snapshots.

Revision ID: m69_005
Revises: m69_004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m69_005"
down_revision = "m69_004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "institutional_event_forecast_snapshots",
        sa.Column("forecast_snapshot_id", sa.String(180), primary_key=True),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("event_session", sa.String(32)),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("snapshot_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("days_to_event", sa.Integer(), nullable=False),
        sa.Column("implied_move_pct", sa.Float()),
        sa.Column("historical_move_pct", sa.Float()),
        sa.Column("forecast_move_pct", sa.Float()),
        sa.Column("expected_move_pct", sa.Float()),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("calculation_method", sa.String(96), nullable=False),
        sa.Column("feature_hash", sa.String(64), nullable=False),
        sa.Column("feature_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "snapshot_date", name="uq_m696_forecast_event_date"),
    )
    op.create_index(
        "ix_m696_forecast_symbol_type_date",
        "institutional_event_forecast_snapshots",
        ["symbol", "event_type", "event_date", "snapshot_date"],
    )
    op.create_index(
        "ix_m696_forecast_event_timestamp",
        "institutional_event_forecast_snapshots",
        ["event_id", "snapshot_timestamp"],
    )

    op.add_column("institutional_event_outcomes", sa.Column("symbol", sa.String(32)))
    op.add_column("institutional_event_outcomes", sa.Column("event_type", sa.String(64)))
    op.add_column("institutional_event_outcomes", sa.Column("event_date", sa.Date()))
    op.add_column("institutional_event_outcomes", sa.Column("event_session", sa.String(32)))
    op.add_column("institutional_event_outcomes", sa.Column("status", sa.String(32), server_default="PROVISIONAL", nullable=False))
    op.add_column("institutional_event_outcomes", sa.Column("forecast_snapshot_id", sa.String(180)))
    op.add_column("institutional_event_outcomes", sa.Column("pre_event_close", sa.Float()))
    op.add_column("institutional_event_outcomes", sa.Column("event_open", sa.Float()))
    op.add_column("institutional_event_outcomes", sa.Column("event_close", sa.Float()))
    op.add_column("institutional_event_outcomes", sa.Column("next_session_open", sa.Float()))
    op.add_column("institutional_event_outcomes", sa.Column("next_session_close", sa.Float()))
    op.add_column("institutional_event_outcomes", sa.Column("gap_move_pct", sa.Float()))
    op.add_column("institutional_event_outcomes", sa.Column("close_to_close_move_pct", sa.Float()))
    op.add_column("institutional_event_outcomes", sa.Column("next_close_move_pct", sa.Float()))
    op.add_column("institutional_event_outcomes", sa.Column("realized_absolute_move_pct", sa.Float()))
    op.add_column("institutional_event_outcomes", sa.Column("prediction_error_pct", sa.Float()))
    op.add_column("institutional_event_outcomes", sa.Column("directional_move_pct", sa.Float()))
    op.add_column("institutional_event_outcomes", sa.Column("finalized_at", sa.DateTime(timezone=True)))
    op.execute("""DELETE FROM institutional_event_outcomes a USING institutional_event_outcomes b WHERE a.event_id=b.event_id AND a.outcome_id>b.outcome_id""")
    op.create_unique_constraint("uq_m696_outcome_event", "institutional_event_outcomes", ["event_id"])
    op.create_index(
        "ix_m696_outcome_symbol_type_date",
        "institutional_event_outcomes",
        ["symbol", "event_type", "event_date", "status"],
    )


def downgrade():
    op.drop_index("ix_m696_outcome_symbol_type_date", table_name="institutional_event_outcomes")
    op.drop_constraint("uq_m696_outcome_event", "institutional_event_outcomes", type_="unique")
    for column in (
        "finalized_at", "directional_move_pct", "prediction_error_pct",
        "realized_absolute_move_pct", "next_close_move_pct", "close_to_close_move_pct",
        "gap_move_pct", "next_session_close", "next_session_open", "event_close",
        "event_open", "pre_event_close", "forecast_snapshot_id", "status",
        "event_session", "event_date", "event_type", "symbol",
    ):
        op.drop_column("institutional_event_outcomes", column)
    op.drop_index("ix_m696_forecast_event_timestamp", table_name="institutional_event_forecast_snapshots")
    op.drop_index("ix_m696_forecast_symbol_type_date", table_name="institutional_event_forecast_snapshots")
    op.drop_table("institutional_event_forecast_snapshots")
