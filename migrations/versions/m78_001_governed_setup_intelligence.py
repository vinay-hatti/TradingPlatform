"""Milestone 78 governed institutional setup intelligence.

Revision ID: m78_001
Revises: m77_004, m42ops
"""
from alembic import op
import sqlalchemy as sa

revision = "m78_001"
down_revision = ("m77_004", "m42ops")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("setup_intelligence_snapshots",
        sa.Column("setup_id",sa.String(160),primary_key=True), sa.Column("candidate_id",sa.String(128),nullable=False),
        sa.Column("scanner_run_id",sa.String(128),nullable=False), sa.Column("symbol",sa.String(32),nullable=False),
        sa.Column("as_of",sa.String(64),nullable=False), sa.Column("setup_type",sa.String(64),nullable=False),
        sa.Column("setup_family",sa.String(48),nullable=False), sa.Column("stage",sa.String(32),nullable=False),
        sa.Column("direction",sa.String(16),nullable=False), sa.Column("quality",sa.Float(),nullable=False),
        sa.Column("confidence",sa.Float(),nullable=False), sa.Column("invalidation_level",sa.Float()),
        sa.Column("entry_reference",sa.Float()), sa.Column("source_state_hash",sa.String(64)),
        sa.Column("context_json",sa.JSON(),nullable=False), sa.Column("evidence_json",sa.JSON(),nullable=False),
        sa.Column("lineage_json",sa.JSON(),nullable=False), sa.Column("authority_effect",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("state_hash",sa.String(64),nullable=False), sa.Column("captured_at",sa.String(64),nullable=False),
        sa.UniqueConstraint("candidate_id","setup_type","as_of",name="uq_m78_candidate_setup_asof"))
    for c in ("candidate_id","scanner_run_id","symbol","as_of","setup_type","setup_family","stage","direction","source_state_hash","state_hash","captured_at"):
        op.create_index(f"ix_setup_intelligence_snapshots_{c}","setup_intelligence_snapshots",[c])

    op.create_table("setup_intelligence_transitions",
        sa.Column("transition_id",sa.String(160),primary_key=True), sa.Column("setup_id",sa.String(160),nullable=False),
        sa.Column("symbol",sa.String(32),nullable=False), sa.Column("setup_type",sa.String(64),nullable=False),
        sa.Column("from_stage",sa.String(32)), sa.Column("to_stage",sa.String(32),nullable=False),
        sa.Column("occurred_at",sa.String(64),nullable=False), sa.Column("reason",sa.Text(),nullable=False), sa.Column("payload_json",sa.JSON(),nullable=False))
    for c in ("setup_id","symbol","setup_type","from_stage","to_stage","occurred_at"):
        op.create_index(f"ix_setup_intelligence_transitions_{c}","setup_intelligence_transitions",[c])

    op.create_table("setup_intelligence_outcomes",
        sa.Column("observation_id",sa.String(160),primary_key=True), sa.Column("setup_id",sa.String(160),nullable=False),
        sa.Column("candidate_id",sa.String(128),nullable=False), sa.Column("symbol",sa.String(32),nullable=False),
        sa.Column("as_of",sa.String(64),nullable=False), sa.Column("setup_type",sa.String(64),nullable=False),
        sa.Column("stage",sa.String(32),nullable=False), sa.Column("direction",sa.String(16),nullable=False),
        sa.Column("market_regime",sa.String(64),nullable=False), sa.Column("gamma_regime",sa.String(64),nullable=False),
        sa.Column("sector_regime",sa.String(64),nullable=False), sa.Column("volatility_regime",sa.String(64),nullable=False),
        sa.Column("label_version",sa.String(96),nullable=False), sa.Column("status",sa.String(48),nullable=False),
        sa.Column("target_1_before_stop",sa.Integer()),sa.Column("target_2_before_stop",sa.Integer()),sa.Column("target_3_before_stop",sa.Integer()),
        sa.Column("thesis_invalidation",sa.Integer()),sa.Column("profitable_at_horizon",sa.Integer()),
        sa.Column("maximum_favorable_excursion_pct",sa.Float()),sa.Column("maximum_adverse_excursion_pct",sa.Float()),
        sa.Column("realized_return_pct",sa.Float()),sa.Column("days_to_target_1",sa.Integer()),sa.Column("days_to_stop",sa.Integer()),
        sa.Column("context_json",sa.JSON(),nullable=False),sa.Column("label_json",sa.JSON(),nullable=False),sa.Column("materialized_at",sa.String(64),nullable=False),
        sa.UniqueConstraint("setup_id","label_version",name="uq_m78_setup_label_version"))
    for c in ("setup_id","candidate_id","symbol","as_of","setup_type","stage","direction","market_regime","gamma_regime","sector_regime","volatility_regime","label_version","status","materialized_at"):
        op.create_index(f"ix_setup_intelligence_outcomes_{c}","setup_intelligence_outcomes",[c])

    op.create_table("setup_probability_model_artifacts",
        sa.Column("model_id",sa.String(160),primary_key=True),sa.Column("model_version",sa.String(96),nullable=False,unique=True),
        sa.Column("lifecycle_state",sa.String(32),nullable=False),sa.Column("sample_size",sa.Integer(),nullable=False),
        sa.Column("training_cutoff",sa.String(64),nullable=False),sa.Column("artifact_json",sa.JSON(),nullable=False),
        sa.Column("evaluation_json",sa.JSON(),nullable=False),sa.Column("governance_json",sa.JSON(),nullable=False),
        sa.Column("state_hash",sa.String(64),nullable=False),sa.Column("created_at",sa.String(64),nullable=False),
        sa.Column("approved_by",sa.String(128)),sa.Column("approved_at",sa.String(64)),sa.Column("activated_by",sa.String(128)),sa.Column("activated_at",sa.String(64)))
    for c in ("model_version","lifecycle_state","training_cutoff","state_hash","created_at"):
        op.create_index(f"ix_setup_probability_model_artifacts_{c}","setup_probability_model_artifacts",[c])

    op.create_table("setup_probability_predictions",
        sa.Column("prediction_id",sa.String(160),primary_key=True),sa.Column("setup_id",sa.String(160),nullable=False),
        sa.Column("symbol",sa.String(32),nullable=False),sa.Column("model_id",sa.String(160),nullable=False),sa.Column("predicted_at",sa.String(64),nullable=False),
        sa.Column("status",sa.String(48),nullable=False),sa.Column("target_1_probability",sa.Float()),sa.Column("profitable_probability",sa.Float()),
        sa.Column("expected_return_pct",sa.Float()),sa.Column("expected_r",sa.Float()),sa.Column("uncertainty",sa.Float(),nullable=False),sa.Column("assessment_json",sa.JSON(),nullable=False),
        sa.UniqueConstraint("setup_id","model_id",name="uq_m78_setup_model_prediction"))
    for c in ("setup_id","symbol","model_id","predicted_at","status"):
        op.create_index(f"ix_setup_probability_predictions_{c}","setup_probability_predictions",[c])

    op.create_table("setup_intelligence_publications",
        sa.Column("publication_id",sa.String(160),primary_key=True),sa.Column("publication_name",sa.String(128),nullable=False),
        sa.Column("source_scanner_run_id",sa.String(128),nullable=False),sa.Column("status",sa.String(32),nullable=False),
        sa.Column("setup_count",sa.Integer(),nullable=False),sa.Column("published_at",sa.String(64),nullable=False),
        sa.Column("payload_json",sa.JSON(),nullable=False),sa.Column("authority_effect",sa.Integer(),nullable=False,server_default="0"))
    for c in ("publication_name","source_scanner_run_id","status","published_at"):
        op.create_index(f"ix_setup_intelligence_publications_{c}","setup_intelligence_publications",[c])

    op.create_table("setup_intelligence_certifications",
        sa.Column("certification_id",sa.String(160),primary_key=True),sa.Column("setup_type",sa.String(64),nullable=False),
        sa.Column("model_id",sa.String(160)),sa.Column("state",sa.String(48),nullable=False),sa.Column("historical_gate",sa.String(48),nullable=False),
        sa.Column("prospective_gate",sa.String(48),nullable=False),sa.Column("evidence_json",sa.JSON(),nullable=False),
        sa.Column("authority_effect",sa.Integer(),nullable=False,server_default="0"),sa.Column("certified_by",sa.String(128)),sa.Column("certified_at",sa.String(64)))
    for c in ("setup_type","model_id","state"):
        op.create_index(f"ix_setup_intelligence_certifications_{c}","setup_intelligence_certifications",[c])

    op.create_table("setup_intelligence_audit_events",
        sa.Column("event_id",sa.String(160),primary_key=True),sa.Column("entity_id",sa.String(160),nullable=False),
        sa.Column("event_type",sa.String(64),nullable=False),sa.Column("actor",sa.String(128),nullable=False),sa.Column("reason",sa.Text(),nullable=False),
        sa.Column("occurred_at",sa.String(64),nullable=False),sa.Column("payload_json",sa.JSON(),nullable=False))
    for c in ("entity_id","event_type","occurred_at"):
        op.create_index(f"ix_setup_intelligence_audit_events_{c}","setup_intelligence_audit_events",[c])


def downgrade():
    for table in ("setup_intelligence_audit_events","setup_intelligence_certifications","setup_intelligence_publications",
                  "setup_probability_predictions","setup_probability_model_artifacts","setup_intelligence_outcomes",
                  "setup_intelligence_transitions","setup_intelligence_snapshots"):
        op.drop_table(table)
