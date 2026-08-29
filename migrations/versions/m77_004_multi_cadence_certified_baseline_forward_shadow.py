"""M77.13 isolated multi-cadence certified-baseline forward shadow.

Revision ID: m77_004
Revises: m77_003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m77_004"
down_revision = "m77_003"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "m77_13_cadence_states",
        sa.Column("state_id", sa.String(128), primary_key=True),
        sa.Column("cadence", sa.String(16), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(32), nullable=False),
        sa.Column("overall_score", sa.Float()),
        sa.Column("confidence", sa.Float()),
        sa.Column("regime", sa.String(64), nullable=False),
        sa.Column("state_hash", sa.String(128)),
        sa.Column("source_replay_run_id", sa.String(128), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("cadence","as_of","symbol", name="uq_m77_13_cadence_state"),
    )
    op.create_index("ix_m77_13_state_cadence_asof","m77_13_cadence_states",["cadence","as_of"])
    op.create_index("ix_m77_13_state_symbol","m77_13_cadence_states",["symbol"])

    op.create_table(
        "m77_13_forward_signals",
        sa.Column("signal_id", sa.String(128), primary_key=True),
        sa.Column("signal_fingerprint", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_as_of", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("baseline_source", sa.String(16), nullable=False),
        sa.Column("baseline_id", sa.String(512), nullable=False),
        sa.Column("horizon_sessions", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(32), nullable=False),
        sa.Column("regime", sa.String(64), nullable=False),
        sa.Column("score_band", sa.String(32), nullable=False),
        sa.Column("confidence_band", sa.String(32), nullable=False),
        sa.Column("reference_price", sa.Float(), nullable=False),
        sa.Column("daily_state_as_of", sa.Date()),
        sa.Column("weekly_state_as_of", sa.Date()),
        sa.Column("monthly_state_as_of", sa.Date()),
        sa.Column("policy_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("signal_fingerprint", name="uq_m77_13_forward_signal_fingerprint"),
    )
    op.create_index("ix_m77_13_signal_status","m77_13_forward_signals",["status"])
    op.create_index("ix_m77_13_signal_source_asof","m77_13_forward_signals",["source_as_of"])
    op.create_index("ix_m77_13_signal_symbol","m77_13_forward_signals",["symbol"])
    op.create_index("ix_m77_13_signal_baseline","m77_13_forward_signals",["baseline_source","horizon_sessions"])

    op.create_table(
        "m77_13_forward_outcomes",
        sa.Column("outcome_id", sa.String(128), primary_key=True),
        sa.Column("signal_id", sa.String(128), sa.ForeignKey("m77_13_forward_signals.signal_id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_session_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_close", sa.Float(), nullable=False),
        sa.Column("raw_return_pct", sa.Float(), nullable=False),
        sa.Column("thesis_return_pct", sa.Float(), nullable=False),
        sa.Column("directional_hit", sa.Boolean(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("signal_id", name="uq_m77_13_forward_outcome_signal"),
    )
    op.create_index("ix_m77_13_outcome_target_date","m77_13_forward_outcomes",["target_session_date"])

def downgrade():
    op.drop_table("m77_13_forward_outcomes")
    op.drop_table("m77_13_forward_signals")
    op.drop_table("m77_13_cadence_states")
