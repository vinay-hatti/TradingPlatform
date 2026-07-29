from __future__ import annotations
import json
from datetime import date, datetime
from sqlalchemy import text
from trading_ai.database.session import SessionLocal


def _to_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])


class TrendIntelligenceRepository:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def latest(self, symbol: str) -> dict | None:
        with self.session_factory() as session:
            row = session.execute(
                text("SELECT payload_json FROM stock_trend_snapshot WHERE symbol=:symbol ORDER BY snapshot_timestamp DESC LIMIT 1"),
                {"symbol": symbol},
            ).scalar_one_or_none()
        if row is None:
            return None
        return row if isinstance(row, dict) else json.loads(row)

    def scanner_context(self, symbol: str, signal: str, maximum_age_days: int = 3, reference_date=None) -> dict:
        snapshot = self.latest(symbol)
        if not snapshot:
            return {"trend_context_status": "MISSING", "trend_score_adjustment": 0.0, "trend_context_warning": "No persisted trend snapshot."}

        snapshot_date = _to_date(snapshot["as_of_date"])
        governed_date = _to_date(reference_date) if reference_date is not None else date.today()
        age = max(0, (governed_date - snapshot_date).days)
        if snapshot_date > governed_date:
            return {"trend_context_status": "FUTURE", "trend_snapshot_date": snapshot["as_of_date"], "trend_snapshot_age_days": age, "trend_score_adjustment": 0.0, "trend_context_warning": "Trend snapshot is newer than the governed market date."}
        if age > maximum_age_days:
            return {"trend_context_status": "STALE", "trend_snapshot_date": snapshot["as_of_date"], "trend_snapshot_age_days": age, "trend_score_adjustment": 0.0, "trend_context_warning": "Trend snapshot exceeds maximum age relative to governed market data."}

        alignment = float(snapshot.get("signal_alignment", {}).get(str(signal).upper(), 50.0))
        quality = float(snapshot.get("trend_quality_score", 50.0))
        confidence = float(snapshot.get("trend_confidence", 50.0))
        raw_adjustment = (alignment - 50.0) * 0.10 + (quality - 50.0) * 0.03 + (confidence - 50.0) * 0.02
        grade = str(snapshot.get('relative_strength_grade', 'UNAVAILABLE')).upper()
        rs_multiplier = {'A+':1.0,'A':1.0,'B':0.90,'C':0.75,'D':0.50,'F':0.0}.get(grade,0.75)
        if raw_adjustment > 0:
            raw_adjustment *= rs_multiplier
        adjustment = max(-6.0, min(6.0, raw_adjustment))
        return {
            "trend_context_status": "FRESH", "trend_snapshot_date": snapshot["as_of_date"], "trend_snapshot_age_days": age,
            "short_term_trend": snapshot["short_term"]["state"], "intermediate_term_trend": snapshot["intermediate_term"]["state"], "long_term_trend": snapshot["long_term"]["state"],
            "trend_alignment_score": float(snapshot["alignment_score"]), "signal_trend_alignment_score": alignment,
            "trend_quality_score": quality, "trend_confidence": confidence, "trend_stage": snapshot.get("trend_stage", ""),
            "trend_age_days": int(snapshot.get("trend_age_days", 0)), "relative_strength_vs_spy": float(snapshot.get("relative_strength_vs_spy", 0)),
            "relative_strength_vs_sector": float(snapshot.get("relative_strength_vs_sector", 0)), "relative_strength_grade": snapshot.get("relative_strength_grade", ""),
            "sector_trend_alignment_score": float(snapshot.get("sector_alignment_score", 50)), "market_trend_alignment_score": float(snapshot.get("market_alignment_score", 50)),
            "trend_score_adjustment": round(adjustment, 2), "trend_context_warning": "",
            "trend_sector": snapshot.get("sector", "Unknown"), "trend_sector_etf": snapshot.get("sector_etf", ""),
            "relative_strength_multiplier": rs_multiplier,
        }
