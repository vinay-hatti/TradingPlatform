from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from sqlalchemy import text



class TrendUniverseType(str, Enum):
    STRONG_BULLISH_ALL = "trend-strong-bullish-all"
    BULLISH_ALIGNMENT = "trend-bullish-alignment"
    EMERGING_BULLISH = "trend-emerging-bullish"
    BULLISH_CONTINUATION = "trend-bullish-continuation"
    PULLBACK_UPTREND = "trend-pullback-uptrend"
    BULLISH_REVERSAL = "trend-bullish-reversal"
    INSTITUTIONAL_BULLISH = "trend-institutional-bullish"
    TOP_BULLISH_SCORE = "trend-top-bullish-score"
    STRONG_BEARISH_ALL = "trend-strong-bearish-all"
    BEARISH_ALIGNMENT = "trend-bearish-alignment"
    EMERGING_BEARISH = "trend-emerging-bearish"
    BEARISH_CONTINUATION = "trend-bearish-continuation"
    PULLBACK_DOWNTREND = "trend-pullback-downtrend"
    BEARISH_REVERSAL = "trend-bearish-reversal"
    INSTITUTIONAL_BEARISH = "trend-institutional-bearish"
    TOP_BEARISH_SCORE = "trend-top-bearish-score"


@dataclass(frozen=True)
class TrendUniverseDefinition:
    universe_id: str
    label: str
    description: str
    empty_message: str


@dataclass(frozen=True)
class TrendUniverseResolution:
    universe_id: str
    symbols: tuple[str, ...]
    snapshot_timestamp: datetime | None
    matched_symbol_count: int
    canonical_symbol_count: int
    excluded_noncanonical_count: int
    status: str
    message: str | None
    criteria_version: str = "trend-universe-v1"


class NoTrendUniverseSymbolsError(ValueError):
    def __init__(self, resolution: TrendUniverseResolution):
        super().__init__(resolution.message or "No symbols currently qualify for the selected trend universe.")
        self.resolution = resolution


DEFINITIONS: tuple[TrendUniverseDefinition, ...] = (
    TrendUniverseDefinition(TrendUniverseType.STRONG_BULLISH_ALL.value, "Strong Bullish — All Timeframes", "All three trend horizons are STRONG_BULLISH.", "No symbols currently have STRONG_BULLISH alignment across all three trend horizons."),
    TrendUniverseDefinition(TrendUniverseType.BULLISH_ALIGNMENT.value, "Bullish Alignment", "All horizons are BULLISH or STRONG_BULLISH, with at least one STRONG_BULLISH horizon.", "No symbols currently qualify for Bullish Alignment."),
    TrendUniverseDefinition(TrendUniverseType.EMERGING_BULLISH.value, "Emerging Bullish", "Short-term strength is leading a constructive intermediate and long-term structure.", "No symbols currently qualify for Emerging Bullish."),
    TrendUniverseDefinition(TrendUniverseType.BULLISH_CONTINUATION.value, "Bullish Trend Continuation", "Strong intermediate and long-term uptrend with constructive short-term continuation.", "No symbols currently qualify for Bullish Trend Continuation."),
    TrendUniverseDefinition(TrendUniverseType.PULLBACK_UPTREND.value, "Pullback in Uptrend", "Short-term pullback inside a bullish intermediate and long-term trend.", "No symbols currently qualify for Pullback in Uptrend."),
    TrendUniverseDefinition(TrendUniverseType.BULLISH_REVERSAL.value, "Bullish Reversal Candidates", "Bullish short-term confirmation with an intermediate reversal against a neutral or bearish long-term state.", "No symbols currently qualify for Bullish Reversal Candidates."),
    TrendUniverseDefinition(TrendUniverseType.INSTITUTIONAL_BULLISH.value, "Institutional Quality Bullish", "High-quality bullish alignment with strong confidence, alignment, and relative strength.", "No symbols currently qualify for Institutional Quality Bullish."),
    TrendUniverseDefinition(TrendUniverseType.TOP_BULLISH_SCORE.value, "Top Bullish Trend Scores", "Highest quality-adjusted bullish composite trend scores.", "No symbols currently have a positive composite bullish trend score."),
    TrendUniverseDefinition(TrendUniverseType.STRONG_BEARISH_ALL.value, "Strong Bearish — All Timeframes", "All three trend horizons are STRONG_BEARISH.", "No symbols currently have STRONG_BEARISH alignment across all three trend horizons."),
    TrendUniverseDefinition(TrendUniverseType.BEARISH_ALIGNMENT.value, "Bearish Alignment", "All horizons are BEARISH or STRONG_BEARISH, with at least one STRONG_BEARISH horizon.", "No symbols currently qualify for Bearish Alignment."),
    TrendUniverseDefinition(TrendUniverseType.EMERGING_BEARISH.value, "Emerging Bearish", "Short-term weakness is leading a constructive bearish intermediate and long-term structure.", "No symbols currently qualify for Emerging Bearish."),
    TrendUniverseDefinition(TrendUniverseType.BEARISH_CONTINUATION.value, "Bearish Trend Continuation", "Strong intermediate and long-term downtrend with constructive short-term continuation.", "No symbols currently qualify for Bearish Trend Continuation."),
    TrendUniverseDefinition(TrendUniverseType.PULLBACK_DOWNTREND.value, "Pullback in Downtrend", "Short-term pullback inside a bearish intermediate and long-term trend.", "No symbols currently qualify for Pullback in Downtrend."),
    TrendUniverseDefinition(TrendUniverseType.BEARISH_REVERSAL.value, "Bearish Reversal Candidates", "Bearish short-term confirmation with an intermediate reversal against a neutral or bullish long-term state.", "No symbols currently qualify for Bearish Reversal Candidates."),
    TrendUniverseDefinition(TrendUniverseType.INSTITUTIONAL_BEARISH.value, "Institutional Quality Bearish", "High-quality bearish alignment with strong confidence, alignment, and relative weakness.", "No symbols currently qualify for Institutional Quality Bearish."),
    TrendUniverseDefinition(TrendUniverseType.TOP_BEARISH_SCORE.value, "Top Bearish Trend Scores", "Lowest quality-adjusted composite trend scores.", "No symbols currently have a negative composite bearish trend score."),
)
DEFINITION_BY_ID = {item.universe_id: item for item in DEFINITIONS}

_LATEST_SQL = text("""
WITH latest_trend AS (
    SELECT DISTINCT ON (symbol)
        symbol, short_term_state, intermediate_term_state, long_term_state,
        alignment_score, trend_quality_score, trend_confidence, trend_stage,
        relative_strength_vs_spy, relative_strength_vs_sector,
        snapshot_timestamp, as_of_date, created_at
    FROM stock_trend_snapshot
    ORDER BY symbol, snapshot_timestamp DESC, as_of_date DESC, created_at DESC
)
SELECT * FROM latest_trend
""")


def is_trend_universe(name: str) -> bool:
    return name.strip().lower().replace("_", "-") in DEFINITION_BY_ID


def _score(value: Any) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return number / 100.0 if abs(number) > 1.0 else number


def _state_score(state: str, intermediate: str, long_term: str) -> float:
    fixed = {"STRONG_BULLISH": 3.0, "BULLISH": 2.0, "SIDEWAYS": 0.0, "BEARISH": -2.0, "STRONG_BEARISH": -3.0}
    if state in fixed:
        return fixed[state]
    context = fixed.get(long_term, fixed.get(intermediate, 0.0))
    if state == "PULLBACK":
        return 1.0 if context > 0 else -1.0 if context < 0 else 0.0
    if state == "REVERSAL":
        return 0.75 if context < 0 else -0.75 if context > 0 else 0.0
    return 0.0


def _composite(row: dict[str, Any]) -> float:
    st, it, lt = row["short_term_state"], row["intermediate_term_state"], row["long_term_state"]
    base = 0.25 * _state_score(st, it, lt) + 0.35 * _state_score(it, st, lt) + 0.40 * _state_score(lt, st, it)
    quality = max(0.25, (_score(row.get("alignment_score")) + _score(row.get("trend_quality_score")) + _score(row.get("trend_confidence"))) / 3.0)
    relative = 0.10 * max(-1.0, min(1.0, float(row.get("relative_strength_vs_spy") or 0.0)))
    return base * quality + relative


def _qualifies(universe_id: str, row: dict[str, Any]) -> bool:
    st, it, lt = row["short_term_state"], row["intermediate_term_state"], row["long_term_state"]
    bull = {"BULLISH", "STRONG_BULLISH"}; bear = {"BEARISH", "STRONG_BEARISH"}
    if universe_id == TrendUniverseType.STRONG_BULLISH_ALL.value: return st == it == lt == "STRONG_BULLISH"
    if universe_id == TrendUniverseType.STRONG_BEARISH_ALL.value: return st == it == lt == "STRONG_BEARISH"
    if universe_id == TrendUniverseType.BULLISH_ALIGNMENT.value: return st in bull and it in bull and lt in bull and "STRONG_BULLISH" in {st,it,lt}
    if universe_id == TrendUniverseType.BEARISH_ALIGNMENT.value: return st in bear and it in bear and lt in bear and "STRONG_BEARISH" in {st,it,lt}
    if universe_id == TrendUniverseType.EMERGING_BULLISH.value: return st == "STRONG_BULLISH" and it in bull and lt in {"SIDEWAYS", *bull} and float(row.get("relative_strength_vs_spy") or 0) > 0
    if universe_id == TrendUniverseType.EMERGING_BEARISH.value: return st == "STRONG_BEARISH" and it in bear and lt in {"SIDEWAYS", *bear} and float(row.get("relative_strength_vs_spy") or 0) < 0
    if universe_id == TrendUniverseType.BULLISH_CONTINUATION.value: return lt == "STRONG_BULLISH" and it == "STRONG_BULLISH" and st in bull and row.get("trend_stage") in {"EARLY_TREND", "ESTABLISHED_TREND"}
    if universe_id == TrendUniverseType.BEARISH_CONTINUATION.value: return lt == "STRONG_BEARISH" and it == "STRONG_BEARISH" and st in bear and row.get("trend_stage") in {"EARLY_TREND", "ESTABLISHED_TREND"}
    if universe_id == TrendUniverseType.PULLBACK_UPTREND.value: return st == "PULLBACK" and it in bull and lt in bull and float(row.get("relative_strength_vs_spy") or 0) > 0 and float(row.get("relative_strength_vs_sector") or 0) >= 0
    if universe_id == TrendUniverseType.PULLBACK_DOWNTREND.value: return st == "PULLBACK" and it in bear and lt in bear and float(row.get("relative_strength_vs_spy") or 0) < 0 and float(row.get("relative_strength_vs_sector") or 0) <= 0
    if universe_id == TrendUniverseType.BULLISH_REVERSAL.value: return st in bull and it == "REVERSAL" and lt in {"SIDEWAYS", *bear}
    if universe_id == TrendUniverseType.BEARISH_REVERSAL.value: return st in bear and it == "REVERSAL" and lt in {"SIDEWAYS", *bull}
    if universe_id == TrendUniverseType.INSTITUTIONAL_BULLISH.value:
        return st in bull and it in bull and lt in bull and [st,it,lt].count("STRONG_BULLISH") >= 2 and min(_score(row.get("alignment_score")), _score(row.get("trend_quality_score")), _score(row.get("trend_confidence"))) >= 0.80 and float(row.get("relative_strength_vs_spy") or 0) > 0 and float(row.get("relative_strength_vs_sector") or 0) > 0 and row.get("trend_stage") in {"EARLY_TREND", "ESTABLISHED_TREND"}
    if universe_id == TrendUniverseType.INSTITUTIONAL_BEARISH.value:
        return st in bear and it in bear and lt in bear and [st,it,lt].count("STRONG_BEARISH") >= 2 and min(_score(row.get("alignment_score")), _score(row.get("trend_quality_score")), _score(row.get("trend_confidence"))) >= 0.80 and float(row.get("relative_strength_vs_spy") or 0) < 0 and float(row.get("relative_strength_vs_sector") or 0) < 0 and row.get("trend_stage") in {"EARLY_TREND", "ESTABLISHED_TREND"}
    return True


class TrendUniverseResolver:
    def __init__(self, session_factory=None, top_score_limit: int = 100):
        if session_factory is None:
            from trading_ai.database import SessionLocal
            session_factory = SessionLocal
        self.session_factory = session_factory
        self.top_score_limit = top_score_limit

    def resolve(self, universe_id: str, canonical_symbols: tuple[str, ...]) -> TrendUniverseResolution:
        normalized = universe_id.strip().lower().replace("_", "-")
        definition = DEFINITION_BY_ID[normalized]
        with self.session_factory() as session:
            rows = [dict(row) for row in session.execute(_LATEST_SQL).mappings().all()]
        canonical = set(canonical_symbols)
        if normalized in {TrendUniverseType.TOP_BULLISH_SCORE.value, TrendUniverseType.TOP_BEARISH_SCORE.value}:
            ranked = sorted(((row, _composite(row)) for row in rows), key=lambda item: item[1], reverse=normalized == TrendUniverseType.TOP_BULLISH_SCORE.value)
            ranked = [item for item in ranked if item[1] > 0] if normalized == TrendUniverseType.TOP_BULLISH_SCORE.value else [item for item in ranked if item[1] < 0]
            matched = [row for row, _ in ranked[: self.top_score_limit]]
        else:
            matched = [row for row in rows if _qualifies(normalized, row)]
        symbols = tuple(sorted({str(row["symbol"]).upper() for row in matched if str(row["symbol"]).upper() in canonical}))
        excluded = len({str(row["symbol"]).upper() for row in matched}) - len(symbols)
        timestamps = [row.get("snapshot_timestamp") for row in matched if row.get("snapshot_timestamp") is not None]
        latest = max(timestamps) if timestamps else None
        message = None if symbols else definition.empty_message
        return TrendUniverseResolution(normalized, symbols, latest, len(matched), len(symbols), excluded, "READY" if symbols else "NO_ELIGIBLE_SYMBOLS", message)
