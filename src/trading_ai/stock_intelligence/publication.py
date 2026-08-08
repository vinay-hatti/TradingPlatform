from __future__ import annotations

from sqlalchemy import desc

from .models import StockScannerCandidateModel, StockScannerPublicationModel


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
        return {"candidate_id": row.id, **dict(row.payload_json or {})}

    @staticmethod
    def _summary(row, payload: dict) -> dict:
        scores = payload.get("scores") or {}
        plan = payload.get("trade_plan") or {}
        entry = plan.get("entry") or {}
        stop = plan.get("stop") or {}
        targets = (plan.get("targets") or {}).get("targets") or []
        context = payload.get("context") or {}
        participation = payload.get("participation") or {}
        breakout = payload.get("breakout") or {}
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
            "breakout_state": breakout.get("state", "NONE"),
            "relative_strength_grade": context.get("relative_strength_grade", ""),
            "dealer_positioning": context.get("dealer_positioning", "UNAVAILABLE"),
            "gamma_regime": context.get("gamma_regime", "UNAVAILABLE"),
            "market_regime": context.get("market_regime", "UNAVAILABLE"),
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
