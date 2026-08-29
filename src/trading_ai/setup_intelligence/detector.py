from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from .contracts import (
    SetupDirection,
    SetupEvidence,
    SetupFamily,
    SetupSnapshot,
    SetupStage,
    SetupType,
)
from .policy import DEFAULT_POLICY, SetupIntelligencePolicy


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        return asdict(value)
    except TypeError:
        return dict(vars(value)) if hasattr(value, "__dict__") else {}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    value = str(value or default).strip().upper()
    return value or default


def _close(payload: dict[str, Any]) -> float:
    states = _dict(payload.get("timeframe_states"))
    for key in ("1d", "1D", "daily", "DAILY"):
        row = _dict(states.get(key))
        if row.get("close") is not None:
            return _num(row.get("close"))
    return _num(payload.get("close"))


def _atr(payload: dict[str, Any]) -> float:
    states = _dict(payload.get("timeframe_states"))
    for key in ("1d", "1D", "daily", "DAILY"):
        row = _dict(states.get(key))
        value = _num(row.get("atr"))
        if value > 0:
            return value
    breakout = _dict(payload.get("breakout"))
    return max(_num(_dict(breakout.get("evidence")).get("atr")), 1e-9)


def _directional_alignment(payload: dict[str, Any], bullish: bool) -> tuple[int, list[str]]:
    wanted = "BULL" if bullish else "BEAR"
    states = _dict(payload.get("timeframe_states"))
    aligned: list[str] = []
    for tf, value in states.items():
        if wanted in _upper(_dict(value).get("direction"), ""):
            aligned.append(str(tf))
    return len(aligned), aligned


def _nearest_level(payload: dict[str, Any], key: str, close: float) -> tuple[float | None, float]:
    values = payload.get(key) or []
    levels = []
    for row in values:
        d = _dict(row)
        price = _num(d.get("price"))
        if price > 0:
            levels.append((price, _num(d.get("strength"), 50.0)))
    if not levels:
        return None, 0.0
    price, strength = min(levels, key=lambda x: abs(close - x[0]))
    return price, strength


def _context(payload: dict[str, Any]) -> dict[str, Any]:
    c = _dict(payload.get("context"))
    metadata = _dict(payload.get("metadata"))
    participation = _dict(payload.get("participation"))
    scores = _dict(payload.get("scores"))
    return {
        "market_regime": _upper(c.get("market_regime")),
        "gamma_regime": _upper(c.get("gamma_regime")),
        "sector_regime": _upper(c.get("sector_regime") or metadata.get("sector_regime")),
        "volatility_regime": _upper(c.get("volatility_regime") or metadata.get("volatility_regime")),
        "participation_state": _upper(participation.get("state")),
        "relative_strength_grade": _upper(c.get("relative_strength_grade")),
        "primary_category": _upper(scores.get("primary_category")),
    }


def _quality(*parts: float) -> float:
    usable = [max(0.0, min(100.0, float(x))) for x in parts if x is not None]
    return round(sum(usable) / len(usable), 2) if usable else 0.0


class GovernedSetupDetector:
    version = "M78-SETUP-DETECTOR-1.0"

    def __init__(self, policy: SetupIntelligencePolicy = DEFAULT_POLICY):
        self.policy = policy

    def detect(
        self,
        candidate: Any,
        *,
        previous: list[Any] | None = None,
    ) -> list[SetupSnapshot]:
        payload = _dict(getattr(candidate, "payload_json", None) or candidate)
        candidate_id = str(getattr(candidate, "id", None) or payload.get("id") or payload.get("candidate_id") or "")
        scanner_run_id = str(getattr(candidate, "scanner_run_id", None) or payload.get("scanner_run_id") or _dict(payload.get("metadata")).get("scanner_run_id") or "")
        symbol = _upper(getattr(candidate, "symbol", None) or payload.get("symbol"), "UNKNOWN")
        as_of = str(getattr(candidate, "snapshot_timestamp", None) or payload.get("snapshot_timestamp") or "")
        source_hash = payload.get("state_hash")
        context = _context(payload)
        close = _close(payload)
        atr = max(_atr(payload), 1e-9)
        direction = _upper(payload.get("direction"), "NEUTRAL")
        scores = _dict(payload.get("scores"))
        breakout = _dict(payload.get("breakout"))
        breakout_state = _upper(breakout.get("state"), "NONE")
        bo_ev = _dict(breakout.get("evidence"))
        resistance = _num(bo_ev.get("resistance")) or None
        support = _num(bo_ev.get("support")) or None
        rv = _num(bo_ev.get("relative_volume"), _num(_dict(payload.get("institutional_volume")).get("relative_volume_1d"), 1.0))
        confirmation = _num(breakout.get("confirmation"))
        follow = _num(breakout.get("follow_through_probability"))
        failure = _num(breakout.get("failure_probability"), 50.0)
        prior = self._prior(previous or [])
        found: list[SetupSnapshot] = []

        def add(stype: SetupType, family: SetupFamily, stage: SetupStage, sdir: SetupDirection, quality: float,
                *, invalidation: float | None = None, reference: float | None = None,
                values: dict[str, Any] | None = None, reasons: list[str] | None = None, blockers: list[str] | None = None) -> None:
            if quality < self.policy.minimum_setup_quality:
                return
            found.append(SetupSnapshot(
                setup_id=f"M78-SETUP-{uuid4().hex.upper()}", candidate_id=candidate_id,
                scanner_run_id=scanner_run_id, symbol=symbol, as_of=as_of,
                setup_type=stype.value, setup_family=family.value, stage=stage.value,
                direction=sdir.value, quality=round(quality, 2), confidence=round(min(100.0, max(0.0, quality)), 2),
                invalidation_level=invalidation, entry_reference=reference or (close or None), source_state_hash=source_hash,
                context=context,
                evidence=SetupEvidence(values=values or {}, reasons=reasons or [], blockers=blockers or []),
                lineage={"detector_version": self.version, "source": "current_stock_intelligence", "point_in_time": True,
                         "future_fields_used": False, "authority_effect": False},
                authority_effect=False,
            ).finalize())

        bull_count, bull_tfs = _directional_alignment(payload, True)
        bear_count, bear_tfs = _directional_alignment(payload, False)
        trend_score = _num(scores.get("trend_continuation"))
        support_level, support_strength = _nearest_level(payload, "support_levels", close)
        resistance_level, resistance_strength = _nearest_level(payload, "resistance_levels", close)
        support_distance_atr = abs(close - support_level) / atr if support_level else 999.0
        resistance_distance_atr = abs(close - resistance_level) / atr if resistance_level else 999.0
        participation = _dict(payload.get("participation"))
        participation_score = _num(participation.get("score"), 50.0)

        # Trend pullback is a first-class setup only when multi-timeframe trend is aligned and price is near structural support.
        if bull_count >= self.policy.minimum_multi_timeframe_alignment and support_distance_atr <= self.policy.max_pullback_support_distance_atr:
            q = _quality(trend_score or _num(scores.get("bullish")), support_strength, max(0.0, 100.0 - support_distance_atr * 80.0), participation_score)
            add(SetupType.TREND_PULLBACK, SetupFamily.TREND, SetupStage.ARMED, SetupDirection.BULLISH, q,
                invalidation=support_level, values={"aligned_timeframes": bull_tfs, "support_distance_atr": round(support_distance_atr, 4),
                "support_strength": support_strength, "relative_volume": rv}, reasons=["Multi-timeframe bullish alignment", "Controlled pullback near structural support"])
        if bear_count >= self.policy.minimum_multi_timeframe_alignment and resistance_distance_atr <= self.policy.max_pullback_support_distance_atr:
            q = _quality(trend_score or _num(scores.get("bearish")), resistance_strength, max(0.0, 100.0 - resistance_distance_atr * 80.0), participation_score)
            add(SetupType.TREND_PULLBACK, SetupFamily.TREND, SetupStage.ARMED, SetupDirection.BEARISH, q,
                invalidation=resistance_level, values={"aligned_timeframes": bear_tfs, "resistance_distance_atr": round(resistance_distance_atr, 4),
                "resistance_strength": resistance_strength, "relative_volume": rv}, reasons=["Multi-timeframe bearish alignment", "Controlled rally into structural resistance"])

        if trend_score >= self.policy.minimum_setup_quality and (bull_count >= 2 or bear_count >= 2):
            sdir = SetupDirection.BULLISH if bull_count >= bear_count else SetupDirection.BEARISH
            add(SetupType.TREND_CONTINUATION, SetupFamily.TREND, SetupStage.CONFIRMED, sdir,
                _quality(trend_score, _num(scores.get("confidence"))), values={"trend_continuation_score": trend_score,
                "bullish_timeframes": bull_tfs, "bearish_timeframes": bear_tfs}, reasons=["Stock Intelligence trend-continuation evidence exceeded governed threshold"])

        self._detect_breakout_lifecycle(add, breakout_state, confirmation, follow, failure, close, atr, resistance, support, rv, prior)

        if breakout_state == "FAILED_BREAKOUT":
            add(SetupType.FAILED_BREAKOUT_REVERSAL, SetupFamily.FAILURE, SetupStage.CONFIRMED, SetupDirection.BEARISH,
                _quality(confirmation, failure, _num(scores.get("reversal"))), invalidation=resistance,
                values={"breakout_state": breakout_state, "failure_probability": failure, "relative_volume": rv},
                reasons=["Previously accepted breakout was rejected back below resistance"])
        if breakout_state == "FAILED_BREAKDOWN":
            add(SetupType.FAILED_BREAKDOWN_REVERSAL, SetupFamily.FAILURE, SetupStage.CONFIRMED, SetupDirection.BULLISH,
                _quality(confirmation, failure, _num(scores.get("reversal"))), invalidation=support,
                values={"breakout_state": breakout_state, "failure_probability": failure, "relative_volume": rv},
                reasons=["Previously accepted breakdown was reclaimed above support"])

        # Structural reversal archetypes preserve support/resistance semantics instead of collapsing to generic BULLISH/BEARISH.
        reversal_score = _num(scores.get("reversal"))
        if support_level and support_distance_atr <= 0.35 and "BULL" in direction:
            add(SetupType.SUPPORT_REVERSAL, SetupFamily.STRUCTURAL_REVERSAL, SetupStage.CONFIRMED, SetupDirection.BULLISH,
                _quality(reversal_score or _num(scores.get("bullish")), support_strength, 100.0 - support_distance_atr * 100.0),
                invalidation=support_level, values={"support_distance_atr": round(support_distance_atr, 4), "support_strength": support_strength},
                reasons=["Bullish state confirmed near high-relevance support"])
        if resistance_level and resistance_distance_atr <= 0.35 and "BEAR" in direction:
            add(SetupType.RESISTANCE_REVERSAL, SetupFamily.STRUCTURAL_REVERSAL, SetupStage.CONFIRMED, SetupDirection.BEARISH,
                _quality(reversal_score or _num(scores.get("bearish")), resistance_strength, 100.0 - resistance_distance_atr * 100.0),
                invalidation=resistance_level, values={"resistance_distance_atr": round(resistance_distance_atr, 4), "resistance_strength": resistance_strength},
                reasons=["Bearish state confirmed near high-relevance resistance"])

        # PEAD is deliberately hypothesis-only until point-in-time earnings evidence exists in the candidate payload.
        event = _dict(payload.get("event_intelligence") or payload.get("event_context") or _dict(payload.get("metadata")).get("event_context"))
        earnings = _dict(event.get("earnings") or event)
        if _upper(earnings.get("event_type"), "") in {"EARNINGS", "EARNINGS_RELEASE"} and earnings.get("surprise_score") is not None:
            surprise = _num(earnings.get("surprise_score"))
            sessions = int(_num(earnings.get("sessions_since_event"), 999))
            revision = _num(earnings.get("revision_score"), 50.0)
            if 1 <= sessions <= 20 and abs(surprise) >= 55:
                sdir = SetupDirection.BULLISH if surprise > 0 else SetupDirection.BEARISH
                stype = SetupType.POST_EARNINGS_DRIFT_LONG if surprise > 0 else SetupType.POST_EARNINGS_DRIFT_SHORT
                q = _quality(abs(surprise), revision, _num(scores.get("confidence")))
                add(stype, SetupFamily.EVENT, SetupStage.ARMED, sdir, q,
                    values={"surprise_score": surprise, "revision_score": revision, "sessions_since_event": sessions},
                    reasons=["Point-in-time earnings surprise and revision evidence satisfy PEAD research prerequisites"])

        return sorted(found, key=lambda x: (-x.quality, x.setup_type))

    @staticmethod
    def _prior(previous: list[Any]) -> dict[str, Any]:
        rows = []
        for row in previous:
            if hasattr(row, "setup_type"):
                rows.append({"setup_type": row.setup_type, "stage": row.stage, "direction": row.direction,
                             "evidence": getattr(row, "evidence_json", {})})
            else:
                rows.append(_dict(row))
        return rows[0] if rows else {}

    def _detect_breakout_lifecycle(self, add, state, confirmation, follow, failure, close, atr, resistance, support, rv, prior):
        values = {"source_breakout_state": state, "confirmation": confirmation, "follow_through": follow,
                  "failure_probability": failure, "relative_volume": rv}
        prior_type = _upper(prior.get("setup_type"), "")
        prior_stage = _upper(prior.get("stage"), "")

        if state == "BREAKOUT_SETUP":
            add(SetupType.BREAKOUT_SETUP, SetupFamily.BREAKOUT, SetupStage.ARMED, SetupDirection.BULLISH,
                _quality(confirmation, follow), invalidation=resistance, reference=resistance, values=values,
                reasons=["Price is within governed breakout setup distance of resistance"])
        elif state == "BREAKOUT_CONFIRMED":
            distance = (close - resistance) / atr if resistance else 0.0
            if prior_type in {"BREAKOUT_CONFIRMED", "BREAKOUT_RETEST", "BREAKOUT_CONTINUATION"}:
                if resistance and abs(close - resistance) / atr <= self.policy.max_retest_distance_atr:
                    add(SetupType.BREAKOUT_RETEST, SetupFamily.BREAKOUT, SetupStage.RETEST_HELD, SetupDirection.BULLISH,
                        _quality(confirmation, follow, 100.0 - failure), invalidation=resistance, reference=resistance,
                        values={**values, "distance_from_level_atr": round(abs(close - resistance) / atr, 4), "prior_stage": prior_stage},
                        reasons=["Prior breakout returned to broken resistance and remains accepted above it"])
                elif distance >= self.policy.min_breakout_hold_distance_atr:
                    add(SetupType.BREAKOUT_CONTINUATION, SetupFamily.BREAKOUT, SetupStage.CONTINUATION, SetupDirection.BULLISH,
                        _quality(confirmation, follow, 100.0 - failure), invalidation=resistance, reference=close,
                        values={**values, "distance_from_level_atr": round(distance, 4), "prior_stage": prior_stage},
                        reasons=["Confirmed breakout remains accepted above resistance across setup snapshots"])
            else:
                add(SetupType.BREAKOUT_CONFIRMED, SetupFamily.BREAKOUT, SetupStage.CONFIRMED, SetupDirection.BULLISH,
                    _quality(confirmation, follow, 100.0 - failure), invalidation=resistance, reference=close, values=values,
                    reasons=["Stock Intelligence confirms breakout above resistance"])
        elif state == "BREAKDOWN_SETUP":
            add(SetupType.BREAKDOWN_SETUP, SetupFamily.BREAKOUT, SetupStage.ARMED, SetupDirection.BEARISH,
                _quality(confirmation, follow), invalidation=support, reference=support, values=values,
                reasons=["Price is within governed breakdown setup distance of support"])
        elif state == "BREAKDOWN_CONFIRMED":
            distance = (support - close) / atr if support else 0.0
            if prior_type in {"BREAKDOWN_CONFIRMED", "BREAKDOWN_RETEST", "BREAKDOWN_CONTINUATION"}:
                if support and abs(close - support) / atr <= self.policy.max_retest_distance_atr:
                    add(SetupType.BREAKDOWN_RETEST, SetupFamily.BREAKOUT, SetupStage.RETEST_HELD, SetupDirection.BEARISH,
                        _quality(confirmation, follow, 100.0 - failure), invalidation=support, reference=support,
                        values={**values, "distance_from_level_atr": round(abs(close - support) / atr, 4), "prior_stage": prior_stage},
                        reasons=["Prior breakdown retested broken support and remains accepted below it"])
                elif distance >= self.policy.min_breakout_hold_distance_atr:
                    add(SetupType.BREAKDOWN_CONTINUATION, SetupFamily.BREAKOUT, SetupStage.CONTINUATION, SetupDirection.BEARISH,
                        _quality(confirmation, follow, 100.0 - failure), invalidation=support, reference=close,
                        values={**values, "distance_from_level_atr": round(distance, 4), "prior_stage": prior_stage},
                        reasons=["Confirmed breakdown remains accepted below support across setup snapshots"])
            else:
                add(SetupType.BREAKDOWN_CONFIRMED, SetupFamily.BREAKOUT, SetupStage.CONFIRMED, SetupDirection.BEARISH,
                    _quality(confirmation, follow, 100.0 - failure), invalidation=support, reference=close, values=values,
                    reasons=["Stock Intelligence confirms breakdown below support"])
