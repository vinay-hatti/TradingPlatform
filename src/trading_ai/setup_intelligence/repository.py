from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import desc, select

from .contracts import SetupSnapshot, stable_hash
from .models import (
    SetupAuditEventModel,
    SetupCertificationModel,
    SetupIntelligencePublicationModel,
    SetupIntelligenceSnapshotModel,
    SetupIntelligenceTransitionModel,
    SetupOutcomeObservationModel,
    SetupProbabilityModelArtifactModel,
    SetupProbabilityPredictionModel,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identity(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex.upper()}"


class SetupIntelligenceRepository:
    def __init__(self, session):
        self.session = session

    def latest_for_symbol(self, symbol: str, limit: int = 5):
        return list(self.session.scalars(select(SetupIntelligenceSnapshotModel).where(
            SetupIntelligenceSnapshotModel.symbol == symbol.upper()).order_by(desc(SetupIntelligenceSnapshotModel.as_of)).limit(limit)))

    def save_snapshot(self, setup: SetupSnapshot) -> SetupIntelligenceSnapshotModel:
        row = self.session.scalar(select(SetupIntelligenceSnapshotModel).where(
            SetupIntelligenceSnapshotModel.candidate_id == setup.candidate_id,
            SetupIntelligenceSnapshotModel.setup_type == setup.setup_type,
            SetupIntelligenceSnapshotModel.as_of == setup.as_of,
        ))
        values = dict(scanner_run_id=setup.scanner_run_id, symbol=setup.symbol, setup_family=setup.setup_family,
                      stage=setup.stage, direction=setup.direction, quality=setup.quality, confidence=setup.confidence,
                      invalidation_level=setup.invalidation_level, entry_reference=setup.entry_reference,
                      source_state_hash=setup.source_state_hash, context_json=setup.context,
                      evidence_json={"values": setup.evidence.values, "reasons": setup.evidence.reasons, "blockers": setup.evidence.blockers},
                      lineage_json=setup.lineage, authority_effect=0, state_hash=setup.state_hash, captured_at=utc_now())
        if row is None:
            row = SetupIntelligenceSnapshotModel(setup_id=setup.setup_id, candidate_id=setup.candidate_id,
                                                 as_of=setup.as_of, setup_type=setup.setup_type, **values)
            self.session.add(row)
        else:
            for k, v in values.items(): setattr(row, k, v)
        self.session.flush()
        return row

    def save_transition(self, setup: SetupSnapshot, previous_stage: str | None, reason: str):
        if previous_stage == setup.stage:
            return None
        row = SetupIntelligenceTransitionModel(transition_id=identity("M78-TRANSITION"), setup_id=setup.setup_id,
            symbol=setup.symbol, setup_type=setup.setup_type, from_stage=previous_stage, to_stage=setup.stage,
            occurred_at=utc_now(), reason=reason, payload_json={"authority_effect": False, "source_candidate_id": setup.candidate_id})
        self.session.add(row); self.session.flush(); return row

    def publish(self, source_run_id: str, count: int, payload: dict):
        row = SetupIntelligencePublicationModel(publication_id=identity("M78-PUB"),
            publication_name="current_setup_intelligence_shadow", source_scanner_run_id=source_run_id,
            status="READY" if count else "EMPTY", setup_count=count, published_at=utc_now(),
            payload_json={**payload, "authority_effect": False, "automatic_promotion": False}, authority_effect=0)
        self.session.add(row); self.session.flush(); return row

    def outcomes(self):
        return list(self.session.scalars(select(SetupOutcomeObservationModel).order_by(
            SetupOutcomeObservationModel.as_of, SetupOutcomeObservationModel.observation_id)))

    def save_outcome(self, setup_row, outcome_row):
        row = self.session.scalar(select(SetupOutcomeObservationModel).where(
            SetupOutcomeObservationModel.setup_id == setup_row.setup_id,
            SetupOutcomeObservationModel.label_version == outcome_row.label_version,
        ))
        ctx = setup_row.context_json or {}
        values = dict(candidate_id=setup_row.candidate_id, symbol=setup_row.symbol, as_of=setup_row.as_of,
            setup_type=setup_row.setup_type, stage=setup_row.stage, direction=setup_row.direction,
            market_regime=str(ctx.get("market_regime") or "UNKNOWN"), gamma_regime=str(ctx.get("gamma_regime") or "UNKNOWN"),
            sector_regime=str(ctx.get("sector_regime") or "UNKNOWN"), volatility_regime=str(ctx.get("volatility_regime") or "UNKNOWN"),
            label_version=outcome_row.label_version, status=outcome_row.status,
            target_1_before_stop=outcome_row.target_1_before_stop, target_2_before_stop=outcome_row.target_2_before_stop,
            target_3_before_stop=outcome_row.target_3_before_stop, thesis_invalidation=outcome_row.thesis_invalidation,
            profitable_at_horizon=outcome_row.profitable_at_horizon,
            maximum_favorable_excursion_pct=outcome_row.maximum_favorable_excursion_pct,
            maximum_adverse_excursion_pct=outcome_row.maximum_adverse_excursion_pct,
            realized_return_pct=outcome_row.realized_return_pct, days_to_target_1=outcome_row.days_to_target_1,
            days_to_stop=outcome_row.days_to_stop, context_json=ctx, label_json=outcome_row.label_json or {}, materialized_at=utc_now())
        if row is None:
            row = SetupOutcomeObservationModel(observation_id=identity("M78-OUTCOME"), setup_id=setup_row.setup_id, **values)
            self.session.add(row)
        else:
            for k, v in values.items(): setattr(row, k, v)
        self.session.flush(); return row

    def save_model(self, model_version: str, artifact: dict, evaluation: dict):
        row = SetupProbabilityModelArtifactModel(model_id=identity("M78-MODEL"), model_version=model_version,
            lifecycle_state="CHALLENGER", sample_size=sum(int(v.get("observations", 0)) for v in evaluation.get("readiness", {}).get("setups", {}).values()),
            training_cutoff=max((k for k in [artifact.get("created_at")] if k), default=utc_now()), artifact_json=artifact,
            evaluation_json=evaluation, governance_json={"automatic_activation": False, "authority_effect": False,
            "prospective_certification_required": True}, state_hash=stable_hash({"artifact": artifact, "evaluation": evaluation}), created_at=utc_now())
        self.session.add(row); self.session.flush(); return row

    def active_shadow_model(self):
        return self.session.scalar(select(SetupProbabilityModelArtifactModel).where(
            SetupProbabilityModelArtifactModel.lifecycle_state == "SHADOW_ACTIVE").order_by(desc(SetupProbabilityModelArtifactModel.activated_at)).limit(1))

    def model(self, model_id: str):
        return self.session.get(SetupProbabilityModelArtifactModel, model_id)

    def save_prediction(self, setup, model, probability, ev):
        row = self.session.scalar(select(SetupProbabilityPredictionModel).where(
            SetupProbabilityPredictionModel.setup_id == setup.setup_id,
            SetupProbabilityPredictionModel.model_id == model.model_id))
        values = dict(symbol=setup.symbol, predicted_at=utc_now(), status=probability.status,
            target_1_probability=probability.target_1_probability, profitable_probability=probability.profitable_probability,
            expected_return_pct=ev.expected_return_pct, expected_r=ev.expected_r,
            uncertainty=round(max(0.0, 1.0 - probability.confidence / 100.0), 8),
            assessment_json={"probability": probability.__dict__, "expected_value": ev.__dict__, "authority_effect": False})
        if row is None:
            row = SetupProbabilityPredictionModel(prediction_id=identity("M78-PRED"), setup_id=setup.setup_id, model_id=model.model_id, **values)
            self.session.add(row)
        else:
            for k, v in values.items(): setattr(row, k, v)
        self.session.flush(); return row

    def audit(self, entity_id: str, event_type: str, actor: str, reason: str, payload: dict):
        row = SetupAuditEventModel(event_id=identity("M78-AUDIT"), entity_id=entity_id, event_type=event_type,
            actor=actor, reason=reason, occurred_at=utc_now(), payload_json={**payload, "authority_effect": False})
        self.session.add(row); self.session.flush(); return row

    def certification_status(self):
        return list(self.session.scalars(select(SetupCertificationModel).order_by(SetupCertificationModel.setup_type)))
