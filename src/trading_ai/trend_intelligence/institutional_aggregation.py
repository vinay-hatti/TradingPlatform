from __future__ import annotations

from collections import Counter
from statistics import mean


def build_institutional_market_overview(results: list[dict]) -> dict:
    """Market Overview-ready aggregate; final UI wiring is performed in Phase 5."""
    if not results:
        return {
            "status": "EMPTY",
            "symbol_count": 0,
            "participation_breadth_pct": 0.0,
            "leadership_breadth_pct": 0.0,
            "deterioration_watch_pct": 0.0,
            "state_distribution": {},
        }
    count = len(results)
    participation = [float(x["participation_score"]) for x in results]
    leadership = [float(x["leadership_score"]) for x in results]
    quality = [float(x["trend_quality_score"]) for x in results]
    deterioration = [float(x["deterioration_risk_score"]) for x in results]
    return {
        "status": "READY",
        "symbol_count": count,
        "average_participation_score": round(mean(participation), 4),
        "average_leadership_score": round(mean(leadership), 4),
        "average_trend_quality_score": round(mean(quality), 4),
        "average_deterioration_risk_score": round(mean(deterioration), 4),
        "participation_breadth_pct": round(100.0 * sum(v >= 60 for v in participation) / count, 4),
        "leadership_breadth_pct": round(100.0 * sum(v >= 60 for v in leadership) / count, 4),
        "deterioration_watch_pct": round(100.0 * sum(v >= 55 for v in deterioration) / count, 4),
        "participation_state_distribution": dict(Counter(x["participation_state"] for x in results)),
        "leadership_state_distribution": dict(Counter(x["leadership_state"] for x in results)),
        "deterioration_state_distribution": dict(Counter(x["deterioration_state"] for x in results)),
    }
