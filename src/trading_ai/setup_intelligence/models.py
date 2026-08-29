from __future__ import annotations

from sqlalchemy import Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from trading_ai.database.base import Base


class SetupIntelligenceSnapshotModel(Base):
    __tablename__ = "setup_intelligence_snapshots"
    __table_args__ = (UniqueConstraint("candidate_id", "setup_type", "as_of", name="uq_m78_candidate_setup_asof"),)

    setup_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    scanner_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    as_of: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    setup_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    setup_family: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    quality: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    invalidation_level: Mapped[float | None] = mapped_column(Float)
    entry_reference: Mapped[float | None] = mapped_column(Float)
    source_state_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    context_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    lineage_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    authority_effect: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    captured_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class SetupIntelligenceTransitionModel(Base):
    __tablename__ = "setup_intelligence_transitions"
    transition_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    setup_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    setup_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    from_stage: Mapped[str | None] = mapped_column(String(32), index=True)
    to_stage: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class SetupOutcomeObservationModel(Base):
    __tablename__ = "setup_intelligence_outcomes"
    __table_args__ = (UniqueConstraint("setup_id", "label_version", name="uq_m78_setup_label_version"),)
    observation_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    setup_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    as_of: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    setup_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    market_regime: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    gamma_regime: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sector_regime: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    volatility_regime: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label_version: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    target_1_before_stop: Mapped[int | None] = mapped_column(Integer)
    target_2_before_stop: Mapped[int | None] = mapped_column(Integer)
    target_3_before_stop: Mapped[int | None] = mapped_column(Integer)
    thesis_invalidation: Mapped[int | None] = mapped_column(Integer)
    profitable_at_horizon: Mapped[int | None] = mapped_column(Integer)
    maximum_favorable_excursion_pct: Mapped[float | None] = mapped_column(Float)
    maximum_adverse_excursion_pct: Mapped[float | None] = mapped_column(Float)
    realized_return_pct: Mapped[float | None] = mapped_column(Float)
    days_to_target_1: Mapped[int | None] = mapped_column(Integer)
    days_to_stop: Mapped[int | None] = mapped_column(Integer)
    context_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    label_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    materialized_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class SetupProbabilityModelArtifactModel(Base):
    __tablename__ = "setup_probability_model_artifacts"
    model_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    model_version: Mapped[str] = mapped_column(String(96), nullable=False, unique=True, index=True)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    training_cutoff: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    evaluation_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    governance_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[str | None] = mapped_column(String(64))
    activated_by: Mapped[str | None] = mapped_column(String(128))
    activated_at: Mapped[str | None] = mapped_column(String(64))


class SetupProbabilityPredictionModel(Base):
    __tablename__ = "setup_probability_predictions"
    __table_args__ = (UniqueConstraint("setup_id", "model_id", name="uq_m78_setup_model_prediction"),)
    prediction_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    setup_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    predicted_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    target_1_probability: Mapped[float | None] = mapped_column(Float)
    profitable_probability: Mapped[float | None] = mapped_column(Float)
    expected_return_pct: Mapped[float | None] = mapped_column(Float)
    expected_r: Mapped[float | None] = mapped_column(Float)
    uncertainty: Mapped[float] = mapped_column(Float, nullable=False)
    assessment_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class SetupIntelligencePublicationModel(Base):
    __tablename__ = "setup_intelligence_publications"
    publication_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    publication_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_scanner_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    setup_count: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    authority_effect: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SetupCertificationModel(Base):
    __tablename__ = "setup_intelligence_certifications"
    certification_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    setup_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_id: Mapped[str | None] = mapped_column(String(160), index=True)
    state: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    historical_gate: Mapped[str] = mapped_column(String(48), nullable=False)
    prospective_gate: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    authority_effect: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    certified_by: Mapped[str | None] = mapped_column(String(128))
    certified_at: Mapped[str | None] = mapped_column(String(64))


class SetupAuditEventModel(Base):
    __tablename__ = "setup_intelligence_audit_events"
    event_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
