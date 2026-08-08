"""Milestone 62 outcome learning.

Revision ID: m62_004
Revises: m62_003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m62_004"
down_revision = "m62_003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "institutional_option_outcome_observations",
        sa.Column("observation_id", sa.String(128), primary_key=True),
        sa.Column("opportunity_id", sa.String(128), nullable=False, unique=True),
        sa.Column("strategy_candidate_id", sa.String(128)),
        sa.Column("setup_category", sa.String(64), nullable=False),
        sa.Column("market_regime", sa.String(64)),
        sa.Column("management_policy", sa.String(64), nullable=False),
        sa.Column("predicted_probability", sa.Float()),
        sa.Column("realized_return_pct", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("exit_reason", sa.String(64), nullable=False),
        sa.Column("entry_timestamp", sa.String(64), nullable=False),
        sa.Column("exit_timestamp", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    for column in ("opportunity_id", "strategy_candidate_id", "setup_category", "market_regime", "management_policy", "outcome", "exit_reason", "entry_timestamp", "exit_timestamp"):
        op.create_index(f"ix_m62_outcome_observation_{column}", "institutional_option_outcome_observations", [column])
    op.create_table(
        "institutional_option_learning_snapshots",
        sa.Column("learning_snapshot_id", sa.String(128), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("scope_value", sa.String(128)),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Float()),
        sa.Column("expectancy_pct", sa.Float()),
        sa.Column("brier_score", sa.Float()),
        sa.Column("expected_calibration_error", sa.Float()),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    for column in ("scope", "scope_value", "created_at"):
        op.create_index(f"ix_m62_learning_{column}", "institutional_option_learning_snapshots", [column])


def downgrade():
    op.drop_table("institutional_option_learning_snapshots")
    op.drop_table("institutional_option_outcome_observations")
