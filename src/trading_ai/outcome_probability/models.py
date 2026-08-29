from __future__ import annotations

from sqlalchemy import Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from trading_ai.database.base import Base


class OutcomeProbabilityObservationModel(Base):
    __tablename__ = "outcome_probability_observations"
    __table_args__ = (
        UniqueConstraint("candidate_id", "label_version", name="uq_m77_candidate_label_version"),
    )

    observation_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    scanner_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    as_of: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    horizon_end: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    label_version: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    feature_version: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    entry_triggered: Mapped[int | None] = mapped_column(Integer)
    target_1_before_stop: Mapped[int | None] = mapped_column(Integer)
    target_2_before_stop: Mapped[int | None] = mapped_column(Integer)
    target_3_before_stop: Mapped[int | None] = mapped_column(Integer)
    profitable_at_horizon: Mapped[int | None] = mapped_column(Integer)
    thesis_invalidation: Mapped[int | None] = mapped_column(Integer)
    maximum_favorable_excursion_pct: Mapped[float | None] = mapped_column(Float)
    maximum_adverse_excursion_pct: Mapped[float | None] = mapped_column(Float)
    realized_return_pct: Mapped[float | None] = mapped_column(Float)
    days_to_target_1: Mapped[int | None] = mapped_column(Integer)
    days_to_stop: Mapped[int | None] = mapped_column(Integer)
    features_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    label_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    lineage_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    materialized_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class OutcomeProbabilityModelArtifactModel(Base):
    __tablename__ = "outcome_probability_model_artifacts"

    model_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    model_version: Mapped[str] = mapped_column(String(96), nullable=False, unique=True, index=True)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    feature_version: Mapped[str] = mapped_column(String(96), nullable=False)
    label_version: Mapped[str] = mapped_column(String(96), nullable=False)
    training_started_at: Mapped[str] = mapped_column(String(64), nullable=False)
    training_completed_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    training_cutoff: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    evaluation_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    governance_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[str | None] = mapped_column(String(64))
    activated_by: Mapped[str | None] = mapped_column(String(128))
    activated_at: Mapped[str | None] = mapped_column(String(64))


class OutcomeProbabilityPredictionModel(Base):
    __tablename__ = "outcome_probability_predictions"
    __table_args__ = (
        UniqueConstraint("candidate_id", "model_id", name="uq_m77_candidate_model_prediction"),
    )

    prediction_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    scanner_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    predicted_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    recommended_disposition: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    target_1_probability: Mapped[float | None] = mapped_column(Float)
    profitable_probability: Mapped[float | None] = mapped_column(Float)
    uncertainty: Mapped[float] = mapped_column(Float, nullable=False)
    assessment_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class OutcomeProbabilityAuditEventModel(Base):
    __tablename__ = "outcome_probability_audit_events"

    event_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
