from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .contracts import BarrierOutcomeLabel, OutcomeProbabilityAssessment, stable_hash
from .features import PointInTimeFeatureBuilder
from .labels import BarrierOutcomeLabeler
from .models import (
    OutcomeProbabilityAuditEventModel,
    OutcomeProbabilityModelArtifactModel,
    OutcomeProbabilityObservationModel,
    OutcomeProbabilityPredictionModel,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identity(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex.upper()}"


class OutcomeProbabilityRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_observation(
        self,
        label: BarrierOutcomeLabel,
        features: dict[str, float],
        lineage: dict,
    ) -> OutcomeProbabilityObservationModel:
        row = self.session.scalar(
            select(OutcomeProbabilityObservationModel).where(
                OutcomeProbabilityObservationModel.candidate_id == label.candidate_id,
                OutcomeProbabilityObservationModel.label_version == BarrierOutcomeLabeler.version,
            )
        )
        values = {
            "scanner_run_id": label.scanner_run_id,
            "symbol": label.symbol,
            "as_of": label.as_of,
            "horizon_end": label.horizon_end,
            "status": label.status,
            "label_version": BarrierOutcomeLabeler.version,
            "feature_version": PointInTimeFeatureBuilder.version,
            "entry_triggered": label.entry_triggered,
            "target_1_before_stop": label.target_1_before_stop,
            "target_2_before_stop": label.target_2_before_stop,
            "target_3_before_stop": label.target_3_before_stop,
            "profitable_at_horizon": label.profitable_at_horizon,
            "thesis_invalidation": label.thesis_invalidation,
            "maximum_favorable_excursion_pct": label.maximum_favorable_excursion_pct,
            "maximum_adverse_excursion_pct": label.maximum_adverse_excursion_pct,
            "realized_return_pct": label.realized_return_pct,
            "days_to_target_1": label.days_to_target_1,
            "days_to_stop": label.days_to_stop,
            "features_json": features,
            "label_json": label.to_dict(),
            "lineage_json": lineage,
            "materialized_at": utc_now(),
        }
        if row is None:
            row = OutcomeProbabilityObservationModel(
                observation_id=identity("M77-OBS"),
                candidate_id=label.candidate_id,
                **values,
            )
            self.session.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        self.session.flush()
        return row

    def observations(self) -> list[OutcomeProbabilityObservationModel]:
        return list(
            self.session.scalars(
                select(OutcomeProbabilityObservationModel).order_by(
                    OutcomeProbabilityObservationModel.as_of,
                    OutcomeProbabilityObservationModel.observation_id,
                )
            )
        )

    def save_model(
        self,
        *,
        model_version: str,
        training_started_at: str,
        training_cutoff: str,
        sample_size: int,
        artifact: dict,
        evaluation: dict,
    ) -> OutcomeProbabilityModelArtifactModel:
        state_hash = stable_hash({"artifact": artifact, "evaluation": evaluation})
        row = OutcomeProbabilityModelArtifactModel(
            model_id=identity("M77-MODEL"),
            model_version=model_version,
            lifecycle_state="CHALLENGER",
            feature_version=PointInTimeFeatureBuilder.version,
            label_version=BarrierOutcomeLabeler.version,
            training_started_at=training_started_at,
            training_completed_at=utc_now(),
            training_cutoff=training_cutoff,
            sample_size=sample_size,
            artifact_json=artifact,
            evaluation_json=evaluation,
            governance_json={
                "automatic_activation": False,
                "authority_effect": False,
                "runtime_mode": "SHADOW",
                "approval_required": True,
            },
            state_hash=state_hash,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def model(self, model_id: str) -> OutcomeProbabilityModelArtifactModel | None:
        return self.session.get(OutcomeProbabilityModelArtifactModel, model_id)

    def active_shadow_model(self) -> OutcomeProbabilityModelArtifactModel | None:
        return self.session.scalar(
            select(OutcomeProbabilityModelArtifactModel)
            .where(OutcomeProbabilityModelArtifactModel.lifecycle_state == "SHADOW_ACTIVE")
            .order_by(OutcomeProbabilityModelArtifactModel.activated_at.desc())
            .limit(1)
        )

    def models(self) -> list[OutcomeProbabilityModelArtifactModel]:
        return list(
            self.session.scalars(
                select(OutcomeProbabilityModelArtifactModel).order_by(
                    OutcomeProbabilityModelArtifactModel.training_completed_at.desc()
                )
            )
        )

    def save_prediction(
        self,
        *,
        candidate_id: str,
        scanner_run_id: str,
        symbol: str,
        assessment: OutcomeProbabilityAssessment,
    ) -> OutcomeProbabilityPredictionModel | None:
        if not assessment.model_id:
            return None
        row = self.session.scalar(
            select(OutcomeProbabilityPredictionModel).where(
                OutcomeProbabilityPredictionModel.candidate_id == candidate_id,
                OutcomeProbabilityPredictionModel.model_id == assessment.model_id,
            )
        )
        if row is None:
            row = OutcomeProbabilityPredictionModel(
                prediction_id=identity("M77-PRED"),
                candidate_id=candidate_id,
                scanner_run_id=scanner_run_id,
                symbol=symbol,
                model_id=assessment.model_id,
                predicted_at=utc_now(),
                mode="SHADOW",
                recommended_disposition=assessment.recommended_disposition,
                target_1_probability=assessment.target_1_before_stop,
                profitable_probability=assessment.profitable_at_horizon,
                uncertainty=assessment.epistemic_uncertainty,
                assessment_json=assessment.to_dict(),
                state_hash=assessment.state_hash,
            )
            self.session.add(row)
            self.session.flush()
        return row

    def audit(self, entity_id: str, event_type: str, actor: str, reason: str, payload: dict) -> None:
        self.session.add(
            OutcomeProbabilityAuditEventModel(
                event_id=identity("M77-AUDIT"),
                entity_id=entity_id,
                event_type=event_type,
                actor=actor,
                reason=reason,
                occurred_at=utc_now(),
                payload_json=payload,
            )
        )
