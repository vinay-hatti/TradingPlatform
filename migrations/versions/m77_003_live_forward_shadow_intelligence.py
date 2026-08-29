"""M77.6 isolated live forward shadow intelligence.

Revision ID: m77_003
Revises: m77_002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m77_003"
down_revision = "m77_002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "m77_shadow_signals",
        sa.Column("signal_id", sa.String(128), primary_key=True),
        sa.Column("signal_fingerprint", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_as_of_date", sa.Date(), nullable=False),
        sa.Column("scanner_run_id", sa.String(128), nullable=False),
        sa.Column("candidate_id", sa.String(128)),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(32), nullable=False),
        sa.Column("primary_category", sa.String(64), nullable=False),
        sa.Column("structure", sa.String(64), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("historical_regime", sa.String(64), nullable=False),
        sa.Column("shadow_tier", sa.String(32), nullable=False),
        sa.Column("candidate_horizon_id", sa.String(512), nullable=False),
        sa.Column("horizon_sessions", sa.Integer(), nullable=False),
        sa.Column("reference_price", sa.Float(), nullable=False),
        sa.Column("state_hash", sa.String(128)),
        sa.Column("policy_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint(
            "signal_fingerprint",
            name="uq_m77_shadow_signal_fingerprint",
        ),
    )
    for column in (
        "source_as_of_date",
        "scanner_run_id",
        "symbol",
        "shadow_tier",
        "status",
        "policy_sha256",
    ):
        op.create_index(
            f"ix_m77_shadow_signals_{column}",
            "m77_shadow_signals",
            [column],
        )

    op.create_table(
        "m77_shadow_outcomes",
        sa.Column("outcome_id", sa.String(128), primary_key=True),
        sa.Column(
            "signal_id",
            sa.String(128),
            sa.ForeignKey(
                "m77_shadow_signals.signal_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("target_session_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_close", sa.Float(), nullable=False),
        sa.Column("raw_return_pct", sa.Float(), nullable=False),
        sa.Column("thesis_return_pct", sa.Float(), nullable=False),
        sa.Column("directional_hit", sa.Boolean(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint(
            "signal_id",
            name="uq_m77_shadow_outcome_signal",
        ),
    )
    op.create_index(
        "ix_m77_shadow_outcomes_target_session_date",
        "m77_shadow_outcomes",
        ["target_session_date"],
    )


def downgrade():
    op.drop_table("m77_shadow_outcomes")
    op.drop_table("m77_shadow_signals")
