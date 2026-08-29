from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, inspect, or_, select
from sqlalchemy.orm import Session

from trading_ai.database.models import PriceHistory
from trading_ai.stock_intelligence.models import StockScannerCandidateModel

from .contracts import OutcomeProbabilityAssessment
from .engine import GovernedOutcomeModelTrainer, OutcomeProbabilityRuntime
from .features import PointInTimeFeatureBuilder
from .labels import BarrierOutcomeLabeler
from .models import OutcomeProbabilityModelArtifactModel, OutcomeProbabilityObservationModel
from .policy import OutcomeProbabilityPolicy
from .repository import OutcomeProbabilityRepository, utc_now


class OutcomeProbabilityService:
    version = "M77.0-GOVERNED-OUTCOME-PROBABILITY-1.0"

    def __init__(self, session: Session, policy: OutcomeProbabilityPolicy | None = None):
        self.session = session
        self.policy = policy or OutcomeProbabilityPolicy()
        self.policy.validate()
        self.repo = OutcomeProbabilityRepository(session)
        self.features = PointInTimeFeatureBuilder()
        self.labeler = BarrierOutcomeLabeler(self.policy)
        self.trainer = GovernedOutcomeModelTrainer(self.policy)

    def data_readiness(self) -> dict[str, Any]:
        candidate_count = int(self.session.scalar(select(func.count()).select_from(StockScannerCandidateModel)) or 0)
        observation_count = int(self.session.scalar(select(func.count()).select_from(OutcomeProbabilityObservationModel)) or 0)
        status_rows = self.session.execute(
            select(OutcomeProbabilityObservationModel.status, func.count())
            .group_by(OutcomeProbabilityObservationModel.status)
        ).all()
        observations = self.repo.observations()
        readiness = self.trainer.readiness(observations)
        return {
            "version": self.version,
            "status": readiness["status"],
            "stock_candidate_snapshots": candidate_count,
            "materialized_observations": observation_count,
            "observation_status_counts": {str(status): int(count) for status, count in status_rows},
            "training_readiness": readiness,
            "label_contract": {
                "version": self.labeler.version,
                "horizon_sessions": self.policy.horizon_sessions,
                "entry_window_sessions": self.policy.entry_window_sessions,
                "same_bar_order_assumed": False,
                "same_bar_target_stop_order_assumed": False,
                "ambiguous_rows_excluded_from_binary_target_training": True,
            },
            "feature_contract": {
                "version": self.features.version,
                "point_in_time_allow_list": True,
                "future_fields_excluded": True,
            },
            "governance": {
                "runtime_mode": "SHADOW",
                "automatic_activation": False,
                "authority_effect": False,
            },
        }

    def materialize_outcomes(self, *, max_candidates: int | None = None) -> dict[str, Any]:
        terminal_statuses = {
            "REALIZED",
            "PARTIALLY_AMBIGUOUS",
            "CENSORED",
            "NO_ENTRY",
            "INVALID_GEOMETRY",
            "INVALID_SNAPSHOT_TIMESTAMP",
        }
        batch_limit = (
            int(max_candidates)
            if max_candidates is not None and max_candidates > 0
            else self.policy.materialization_batch_size
        )
        observation = OutcomeProbabilityObservationModel
        query = (
            select(StockScannerCandidateModel)
            .outerjoin(
                observation,
                and_(
                    observation.candidate_id == StockScannerCandidateModel.id,
                    observation.label_version == self.labeler.version,
                ),
            )
            .where(
                or_(
                    observation.observation_id.is_(None),
                    observation.status.notin_(terminal_statuses),
                )
            )
            .order_by(
                StockScannerCandidateModel.snapshot_timestamp,
                StockScannerCandidateModel.id,
            )
            .limit(batch_limit)
        )
        pending_candidates = list(self.session.scalars(query))
        finalized_count = int(
            self.session.scalar(
                select(func.count())
                .select_from(observation)
                .where(
                    observation.label_version == self.labeler.version,
                    observation.status.in_(terminal_statuses),
                )
            )
            or 0
        )
        by_symbol: dict[str, list[StockScannerCandidateModel]] = {}
        for candidate in pending_candidates:
            by_symbol.setdefault(str(candidate.symbol).upper(), []).append(candidate)
        counts: dict[str, int] = {}
        for symbol, rows in sorted(by_symbol.items()):
            bars = list(
                self.session.scalars(
                    select(PriceHistory)
                    .where(func.upper(PriceHistory.symbol) == symbol)
                    .order_by(PriceHistory.date)
                )
            )
            for candidate in rows:
                payload = dict(candidate.payload_json or {})
                label = self.labeler.label(
                    candidate_id=candidate.id,
                    scanner_run_id=candidate.scanner_run_id,
                    candidate_payload=payload,
                    future_bars=bars,
                )
                feature_values = self.features.build(payload)
                lineage = {
                    **self.features.lineage(payload),
                    "candidate_id": candidate.id,
                    "scanner_run_id": candidate.scanner_run_id,
                    "direction": payload.get("direction"),
                    "category": (payload.get("scores") or {}).get("primary_category"),
                    "market_regime": (payload.get("context") or {}).get("market_regime"),
                    "label_version": self.labeler.version,
                }
                self.repo.save_observation(label, feature_values, lineage)
                counts[label.status] = counts.get(label.status, 0) + 1
        self.session.commit()
        return {
            "version": self.version,
            "status": "COMPLETE",
            "batch_limit": batch_limit,
            "candidates_examined": len(pending_candidates),
            "candidates_processed": len(pending_candidates),
            "candidates_skipped_finalized": finalized_count,
            "status_counts": counts,
            "data_readiness": self.data_readiness(),
        }

    def train_challenger(self, *, model_version: str | None = None) -> dict[str, Any]:
        started = utc_now()
        observations = self.repo.observations()
        eligible = self.trainer.eligible_observations(observations)
        readiness = self.trainer.readiness(eligible)
        if readiness["status"] != "READY":
            return {
                "version": self.version,
                "status": "INSUFFICIENT_EVIDENCE",
                "model_created": False,
                "readiness": readiness,
            }
        artifact, evaluation = self.trainer.train(observations)
        resolved_version = model_version or datetime.now(timezone.utc).strftime("M77-OUTCOME-%Y%m%dT%H%M%SZ")
        row = self.repo.save_model(
            model_version=resolved_version,
            training_started_at=started,
            training_cutoff=max(str(row.as_of) for row in eligible),
            sample_size=len(eligible),
            artifact=artifact,
            evaluation=evaluation,
        )
        self.repo.audit(
            row.model_id,
            "CHALLENGER_TRAINED",
            "m77-training-service",
            "Chronological M77 challenger training completed",
            {"evaluation": evaluation, "state_hash": row.state_hash},
        )
        self.session.commit()
        return {"version": self.version, "status": "CHALLENGER_CREATED", "model": self.model_dto(row)}

    def approve_shadow_model(self, model_id: str, *, actor: str, reason: str) -> dict[str, Any]:
        row = self._require_model(model_id)
        if row.lifecycle_state != "CHALLENGER":
            raise ValueError(f"Model must be CHALLENGER, observed {row.lifecycle_state}")
        if not bool((row.evaluation_json or {}).get("promotion_eligible")):
            raise ValueError("Model failed governed out-of-sample promotion gates")
        if not actor.strip() or not reason.strip():
            raise ValueError("Explicit actor and reason are required")
        row.lifecycle_state = "APPROVED_SHADOW"
        row.approved_by = actor
        row.approved_at = utc_now()
        self.repo.audit(row.model_id, "SHADOW_MODEL_APPROVED", actor, reason, {"state_hash": row.state_hash})
        self.session.commit()
        return self.model_dto(row)

    def activate_shadow_model(self, model_id: str, *, actor: str, reason: str) -> dict[str, Any]:
        row = self._require_model(model_id)
        if row.lifecycle_state != "APPROVED_SHADOW":
            raise ValueError(f"Model must be APPROVED_SHADOW, observed {row.lifecycle_state}")
        if not actor.strip() or not reason.strip():
            raise ValueError("Explicit actor and reason are required")
        for active in self.session.scalars(
            select(OutcomeProbabilityModelArtifactModel).where(
                OutcomeProbabilityModelArtifactModel.lifecycle_state == "SHADOW_ACTIVE"
            ).with_for_update()
        ):
            active.lifecycle_state = "RETIRED"
            self.repo.audit(active.model_id, "SHADOW_MODEL_RETIRED", actor, reason, {"successor": row.model_id})
        row.lifecycle_state = "SHADOW_ACTIVE"
        row.activated_by = actor
        row.activated_at = utc_now()
        self.repo.audit(
            row.model_id,
            "SHADOW_MODEL_ACTIVATED",
            actor,
            reason,
            {"authority_effect": False, "automatic_activation": False},
        )
        self.session.commit()
        return self.model_dto(row)

    def build_runtime(self) -> OutcomeProbabilityRuntime | None:
        get_bind = getattr(self.session, "get_bind", None)
        if not callable(get_bind):
            return None
        try:
            table_available = inspect(get_bind()).has_table(
                OutcomeProbabilityModelArtifactModel.__tablename__
            )
        except Exception:
            # M77 is additive shadow evidence and must never interrupt the
            # authoritative Stock Intelligence path if its storage is absent.
            return None
        if not table_available:
            return None
        row = self.repo.active_shadow_model()
        if row is None:
            return None
        analogs = [
            value
            for value in self.repo.observations()
            if value.entry_triggered == 1
            and value.status in {"REALIZED", "PARTIALLY_AMBIGUOUS", "CENSORED"}
        ]
        return OutcomeProbabilityRuntime(
            model_id=row.model_id,
            model_version=row.model_version,
            artifact=dict(row.artifact_json or {}),
            observations=analogs,
            policy=self.policy,
        )

    def attach_shadow_assessment(
        self,
        profile: Any,
        runtime: OutcomeProbabilityRuntime | None,
    ) -> OutcomeProbabilityAssessment:
        if runtime is None:
            assessment = OutcomeProbabilityAssessment(
                warnings=[
                    "NO_APPROVED_SHADOW_MODEL",
                    "DETERMINISTIC_M76_BARRIER_PRIOR_REMAINS_AUTHORITATIVE_INPUT",
                ],
                lineage={
                    **self.features.lineage(profile),
                    "runtime_mode": "SHADOW",
                    "authority_effect": False,
                },
            ).finalize()
        else:
            assessment = runtime.score(profile)
        decision = getattr(profile, "decision_intelligence", None)
        if decision is not None:
            decision.outcome_probability = assessment.to_dict()
            finalize_decision = getattr(decision, "finalize", None)
            if callable(finalize_decision):
                finalize_decision()
        finalize_profile = getattr(profile, "finalize", None)
        if callable(finalize_profile):
            finalize_profile()
        return assessment

    def record_prediction(
        self,
        *,
        candidate_id: str,
        scanner_run_id: str,
        symbol: str,
        assessment: OutcomeProbabilityAssessment,
    ) -> None:
        self.repo.save_prediction(
            candidate_id=candidate_id,
            scanner_run_id=scanner_run_id,
            symbol=symbol,
            assessment=assessment,
        )

    def status(self) -> dict[str, Any]:
        active = self.repo.active_shadow_model()
        return {
            "version": self.version,
            "runtime_mode": "SHADOW",
            "authority_effect": False,
            "automatic_activation": False,
            "active_shadow_model": None if active is None else self.model_dto(active),
            "models": [self.model_dto(row) for row in self.repo.models()],
            "data_readiness": self.data_readiness(),
        }

    @staticmethod
    def model_dto(row: OutcomeProbabilityModelArtifactModel) -> dict[str, Any]:
        return {
            "model_id": row.model_id,
            "model_version": row.model_version,
            "lifecycle_state": row.lifecycle_state,
            "feature_version": row.feature_version,
            "label_version": row.label_version,
            "sample_size": row.sample_size,
            "training_cutoff": row.training_cutoff,
            "training_completed_at": row.training_completed_at,
            "evaluation": row.evaluation_json,
            "governance": row.governance_json,
            "state_hash": row.state_hash,
            "approved_by": row.approved_by,
            "approved_at": row.approved_at,
            "activated_by": row.activated_by,
            "activated_at": row.activated_at,
        }

    def _require_model(self, model_id: str) -> OutcomeProbabilityModelArtifactModel:
        row = self.repo.model(model_id)
        if row is None:
            raise KeyError(f"M77 model not found: {model_id}")
        return row
