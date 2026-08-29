from __future__ import annotations

from sqlalchemy import desc

from .models import StockScannerCandidateModel, StockScannerPublicationModel
from .volume_response_classifier import InstitutionalVolumeResponseClassifier


class StockScannerPublicationService:
    def __init__(self, session):
        self.session = session

    def latest_publication(self, publication_name: str = "current_stock_intelligence"):
        return (
            self.session.query(StockScannerPublicationModel)
            .filter(StockScannerPublicationModel.publication_name == publication_name)
            .filter(StockScannerPublicationModel.status.in_(("READY", "DEGRADED")))
            .order_by(desc(StockScannerPublicationModel.snapshot_timestamp))
            .first()
        )

    def candidates(
        self,
        *,
        publication_name: str = "current_stock_intelligence",
        category: str | None = None,
        direction: str | None = None,
        structure: str | None = None,
        min_score: float = 0.0,
        min_confidence: float = 0.0,
        search: str | None = None,
        limit: int = 2000,
    ) -> tuple[object | None, list[dict]]:
        publication = self.latest_publication(publication_name)
        if publication is None:
            return None, []
        query = (
            self.session.query(StockScannerCandidateModel)
            .filter(StockScannerCandidateModel.scanner_run_id == publication.scanner_run_id)
            .filter(StockScannerCandidateModel.score >= float(min_score))
        )
        if category:
            query = query.filter(StockScannerCandidateModel.category == category.upper())
        if search:
            query = query.filter(StockScannerCandidateModel.symbol.ilike(f"%{search.strip()}%"))
        rows = query.order_by(desc(StockScannerCandidateModel.score), StockScannerCandidateModel.symbol).limit(limit).all()
        values = []
        for row in rows:
            payload = dict(row.payload_json or {})
            scores = payload.get("scores") or {}
            if float(scores.get("confidence", 0)) < min_confidence:
                continue
            if direction and str(payload.get("direction", "")).upper() != direction.upper():
                continue
            if structure and str(payload.get("structure", "")).upper() != structure.upper():
                continue
            values.append(self._summary(row, payload))
        return publication, values

    def candidate(self, candidate_id: str) -> dict | None:
        row = self.session.get(StockScannerCandidateModel, candidate_id)
        if row is None:
            return None
        payload = dict(row.payload_json or {})
        return {
            "candidate_id": row.id,
            **payload,
            "volume_response_interpretation": InstitutionalVolumeResponseClassifier().classify(payload),
        }

    @staticmethod
    def _summary(row, payload: dict) -> dict:
        scores = payload.get("scores") or {}
        plan = payload.get("trade_plan") or {}
        entry = plan.get("entry") or {}
        stop = plan.get("stop") or {}
        targets = (plan.get("targets") or {}).get("targets") or []
        context = payload.get("context") or {}
        certification = plan.get("certification") or {}
        reference_market = plan.get("reference_market") or certification.get("reference_market") or {}
        participation = payload.get("participation") or {}
        volume = payload.get("institutional_volume") or {}
        breakout = payload.get("breakout") or {}
        decision = payload.get("decision_intelligence") or {}
        barrier = decision.get("barrier_probability") or {}
        outcome_probability = decision.get("outcome_probability") or {}
        competition = decision.get("competition") or {}
        states = payload.get("timeframe_states") or {}
        return {
            "candidate_id": row.id,
            "symbol": row.symbol,
            "rank": (payload.get("metadata") or {}).get("rank"),
            "primary_category": scores.get("primary_category", row.category),
            "score": scores.get("overall", row.score),
            "confidence": scores.get("confidence", 0),
            "freshness": scores.get("freshness", 0),
            "direction": payload.get("direction", "NEUTRAL"),
            "structure": payload.get("structure", "SIDEWAYS"),
            "primary_timeframe": payload.get("primary_timeframe", "1d"),
            "alignment_score": payload.get("alignment_score", 0),
            "participation_state": participation.get("state", "NEUTRAL"),
            "institutional_volume_score": volume.get("institutional_participation_score", 50),
            "institutional_volume_regime": volume.get("regime", "UNAVAILABLE"),
            "institutional_volume_signal": volume.get("signal", "UNAVAILABLE"),
            "relative_volume_1d": volume.get("relative_volume_1d", 0),
            "volume_persistence_score": volume.get("persistence_score", 0),
            "volume_dry_up_score": volume.get("dry_up_score", 0),
            "volume_absorption_score": volume.get("absorption_score", 0),
            "breakout_volume_confirmation": volume.get("breakout_confirmation_score", 0),
            "breakdown_volume_confirmation": volume.get("breakdown_confirmation_score", 0),
            "breakout_state": breakout.get("state", "NONE"),
            "institutional_trade_quality": decision.get("overall_trade_quality"),
            "decision_readiness": decision.get("decision_readiness"),
            "capital_priority": decision.get("capital_priority"),
            "opportunity_freshness": decision.get("opportunity_freshness"),
            "institutional_grade": decision.get("institutional_grade"),
            "institutional_decision": decision.get("decision"),
            "opportunity_lifecycle": decision.get("opportunity_lifecycle"),
            "barrier_target_1_probability": barrier.get("target_1_before_stop"),
            "barrier_target_2_probability": barrier.get("target_2_before_stop"),
            "barrier_target_3_probability": barrier.get("target_3_before_stop"),
            "expected_mfe_pct": barrier.get("expected_mfe_pct"),
            "expected_mae_pct": barrier.get("expected_mae_pct"),
            "outcome_probability_status": outcome_probability.get("status"),
            "outcome_probability_disposition": outcome_probability.get("recommended_disposition"),
            "outcome_probability_target_1": outcome_probability.get("target_1_before_stop"),
            "outcome_probability_target_2": outcome_probability.get("target_2_before_stop"),
            "outcome_probability_profitable_horizon": outcome_probability.get("profitable_at_horizon"),
            "outcome_probability_expected_value_r": outcome_probability.get("expected_value_r"),
            "outcome_probability_uncertainty": outcome_probability.get("epistemic_uncertainty"),
            "outcome_probability": outcome_probability,
            "decision_market_rank": competition.get("market_rank"),
            "decision_population_size": competition.get("population_size"),
            "decision_market_percentile": competition.get("market_percentile"),
            "decision_intelligence": decision,
            "relative_strength_grade": context.get("relative_strength_grade", ""),
            "dealer_positioning": context.get("dealer_positioning", "UNAVAILABLE"),
            "gamma_regime": context.get("gamma_regime", "UNAVAILABLE"),
            "market_regime": context.get("market_regime", "UNAVAILABLE"),
            "underlying_reference_price": reference_market.get("price"),
            "underlying_reference_timestamp": reference_market.get("timestamp"),
            "underlying_reference_source": reference_market.get("source", "LATEST_UNDERLYING_INGESTION"),
            "underlying_reference_freshness_minutes": reference_market.get("freshness_minutes_at_certification"),
            "trade_plan_certification": certification,
            "trade_plan_certification_status": certification.get("status", "NOT_CERTIFIED"),
            "trade_plan_quality_score": certification.get("quality_score"),
            "entry_zone_low": entry.get("zone_low"),
            "entry_zone_high": entry.get("zone_high"),
            "recommended_stop": stop.get("recommended_stop"),
            "targets": [item.get("price") for item in targets[:3]],
            "additional_targets": ((plan.get("targets") or {}).get("additional_targets") or []),
            "structural_reward_risk": plan.get("structural_reward_risk", 0),
            "management_quality": plan.get("management_quality", 0),
            "timeframes": {key: {"direction": value.get("direction"), "structure": value.get("structure"), "confidence": value.get("confidence")} for key, value in states.items()},
            "snapshot_timestamp": row.snapshot_timestamp,
            "state_hash": payload.get("state_hash", ""),
            "warnings": payload.get("warnings", []),
        }
