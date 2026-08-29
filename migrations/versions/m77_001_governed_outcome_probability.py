"""M77 governed outcome probability and meta-labeling.

Revision ID: m77_001
Revises: m73_002
"""

from alembic import op
import sqlalchemy as sa


revision = "m77_001"
down_revision = "m73_002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "outcome_probability_observations",
        sa.Column("observation_id", sa.String(160), primary_key=True),
        sa.Column("candidate_id", sa.String(128), nullable=False),
        sa.Column("scanner_run_id", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("as_of", sa.String(64), nullable=False),
        sa.Column("horizon_end", sa.String(64)),
        sa.Column("status", sa.String(48), nullable=False),
        sa.Column("label_version", sa.String(96), nullable=False),
        sa.Column("feature_version", sa.String(96), nullable=False),
        sa.Column("entry_triggered", sa.Integer()),
        sa.Column("target_1_before_stop", sa.Integer()),
        sa.Column("target_2_before_stop", sa.Integer()),
        sa.Column("target_3_before_stop", sa.Integer()),
        sa.Column("profitable_at_horizon", sa.Integer()),
        sa.Column("thesis_invalidation", sa.Integer()),
        sa.Column("maximum_favorable_excursion_pct", sa.Float()),
        sa.Column("maximum_adverse_excursion_pct", sa.Float()),
        sa.Column("realized_return_pct", sa.Float()),
        sa.Column("days_to_target_1", sa.Integer()),
        sa.Column("days_to_stop", sa.Integer()),
        sa.Column("features_json", sa.JSON(), nullable=False),
        sa.Column("label_json", sa.JSON(), nullable=False),
        sa.Column("lineage_json", sa.JSON(), nullable=False),
        sa.Column("materialized_at", sa.String(64), nullable=False),
        sa.UniqueConstraint("candidate_id", "label_version", name="uq_m77_candidate_label_version"),
    )
    for name, column in (
        ("ix_m77_obs_candidate", "candidate_id"),
        ("ix_m77_obs_run", "scanner_run_id"),
        ("ix_m77_obs_symbol", "symbol"),
        ("ix_m77_obs_as_of", "as_of"),
        ("ix_m77_obs_horizon", "horizon_end"),
        ("ix_m77_obs_status", "status"),
        ("ix_m77_obs_label_version", "label_version"),
        ("ix_m77_obs_feature_version", "feature_version"),
        ("ix_m77_obs_materialized", "materialized_at"),
    ):
        op.create_index(name, "outcome_probability_observations", [column])

    op.create_table(
        "outcome_probability_model_artifacts",
        sa.Column("model_id", sa.String(160), primary_key=True),
        sa.Column("model_version", sa.String(96), nullable=False, unique=True),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("feature_version", sa.String(96), nullable=False),
        sa.Column("label_version", sa.String(96), nullable=False),
        sa.Column("training_started_at", sa.String(64), nullable=False),
        sa.Column("training_completed_at", sa.String(64), nullable=False),
        sa.Column("training_cutoff", sa.String(64), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("artifact_json", sa.JSON(), nullable=False),
        sa.Column("evaluation_json", sa.JSON(), nullable=False),
        sa.Column("governance_json", sa.JSON(), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("approved_by", sa.String(128)),
        sa.Column("approved_at", sa.String(64)),
        sa.Column("activated_by", sa.String(128)),
        sa.Column("activated_at", sa.String(64)),
    )
    for name, column in (
        ("ix_m77_model_version", "model_version"),
        ("ix_m77_model_state", "lifecycle_state"),
        ("ix_m77_model_completed", "training_completed_at"),
        ("ix_m77_model_cutoff", "training_cutoff"),
        ("ix_m77_model_hash", "state_hash"),
    ):
        op.create_index(name, "outcome_probability_model_artifacts", [column])
    op.create_index(
        "uq_m77_one_shadow_active",
        "outcome_probability_model_artifacts",
        ["lifecycle_state"],
        unique=True,
        postgresql_where=sa.text("lifecycle_state = 'SHADOW_ACTIVE'"),
    )

    op.create_table(
        "outcome_probability_predictions",
        sa.Column("prediction_id", sa.String(160), primary_key=True),
        sa.Column("candidate_id", sa.String(128), nullable=False),
        sa.Column("scanner_run_id", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("predicted_at", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("recommended_disposition", sa.String(24), nullable=False),
        sa.Column("target_1_probability", sa.Float()),
        sa.Column("profitable_probability", sa.Float()),
        sa.Column("uncertainty", sa.Float(), nullable=False),
        sa.Column("assessment_json", sa.JSON(), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("candidate_id", "model_id", name="uq_m77_candidate_model_prediction"),
    )
    for name, column in (
        ("ix_m77_pred_candidate", "candidate_id"),
        ("ix_m77_pred_run", "scanner_run_id"),
        ("ix_m77_pred_symbol", "symbol"),
        ("ix_m77_pred_model", "model_id"),
        ("ix_m77_pred_at", "predicted_at"),
        ("ix_m77_pred_mode", "mode"),
        ("ix_m77_pred_disposition", "recommended_disposition"),
        ("ix_m77_pred_hash", "state_hash"),
    ):
        op.create_index(name, "outcome_probability_predictions", [column])

    op.create_table(
        "outcome_probability_audit_events",
        sa.Column("event_id", sa.String(160), primary_key=True),
        sa.Column("entity_id", sa.String(160), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_m77_audit_entity", "outcome_probability_audit_events", ["entity_id"])
    op.create_index("ix_m77_audit_type", "outcome_probability_audit_events", ["event_type"])
    op.create_index("ix_m77_audit_at", "outcome_probability_audit_events", ["occurred_at"])


def downgrade():
    op.drop_table("outcome_probability_audit_events")
    op.drop_table("outcome_probability_predictions")
    op.drop_table("outcome_probability_model_artifacts")
    op.drop_table("outcome_probability_observations")
