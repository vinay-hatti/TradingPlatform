from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


NUMERIC_FEATURES = (
    "directional_quality",
    "trend_quality",
    "structure_quality",
    "breakout_quality",
    "institutional_volume_quality",
    "participation_quality",
    "relative_strength_quality",
    "market_alignment",
    "dealer_quality",
    "liquidity_quality",
    "risk_quality",
    "management_quality",
    "certification_quality",
    "overall_trade_quality",
    "decision_readiness",
    "opportunity_freshness",
    "alignment_score",
    "scanner_score",
    "scanner_confidence",
    "relative_volume_1d",
    "volume_persistence",
    "breakout_confirmation",
    "breakout_follow_through",
    "breakout_failure",
    "structural_reward_risk",
    "entry_extension_atr",
    "bullish_direction",
    "bearish_direction",
    "accumulation_setup",
    "distribution_setup",
    "breakout_setup",
    "mean_reversion_setup",
    "uptrend_regime",
    "downtrend_regime",
    "negative_gamma_regime",
)

FORBIDDEN_FEATURE_TOKENS = (
    "outcome",
    "realized",
    "future",
    "target_hit",
    "stop_hit",
    "maximum_favorable",
    "maximum_adverse",
    "closed_at",
)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    return dict(vars(value)) if value is not None and hasattr(value, "__dict__") else {}


class PointInTimeFeatureBuilder:
    """Extracts an explicit allow-list from the immutable candidate snapshot."""

    version = "M77.0-POINT-IN-TIME-FEATURES-1.0"

    def build(self, candidate: Any) -> dict[str, float]:
        payload = _dict(candidate)
        scores = _dict(payload.get("scores"))
        decision = _dict(payload.get("decision_intelligence"))
        vector = _dict(decision.get("quality_vector"))
        explain = _dict(decision.get("explainability"))
        freshness = _dict(explain.get("opportunity_freshness"))
        volume = _dict(payload.get("institutional_volume"))
        participation = _dict(payload.get("participation"))
        breakout = _dict(payload.get("breakout"))
        context = _dict(payload.get("context"))
        plan = _dict(payload.get("trade_plan"))
        certification = _dict(plan.get("certification"))
        direction = str(payload.get("direction") or "").upper()
        category = str(scores.get("primary_category") or "").upper()
        regime = str(context.get("market_regime") or "").upper()
        gamma = str(context.get("gamma_regime") or "").upper()

        raw = {
            **{name: _number(vector.get(name)) for name in NUMERIC_FEATURES},
            "overall_trade_quality": _number(decision.get("overall_trade_quality")),
            "decision_readiness": _number(decision.get("decision_readiness")),
            "opportunity_freshness": _number(decision.get("opportunity_freshness")),
            "alignment_score": _number(payload.get("alignment_score")),
            "scanner_score": _number(scores.get("overall")),
            "scanner_confidence": _number(scores.get("confidence")),
            "relative_volume_1d": _number(volume.get("relative_volume_1d")),
            "volume_persistence": _number(volume.get("persistence_score")),
            "breakout_confirmation": _number(breakout.get("confirmation")),
            "breakout_follow_through": _number(breakout.get("follow_through_probability")),
            "breakout_failure": _number(breakout.get("failure_probability")),
            "structural_reward_risk": _number(plan.get("structural_reward_risk")),
            "entry_extension_atr": _number(freshness.get("extension_atr")),
            "management_quality": _number(plan.get("management_quality")),
            "certification_quality": _number(certification.get("quality_score")),
            "participation_quality": _number(
                vector.get("participation_quality"),
                _number(participation.get("score")),
            ),
            "bullish_direction": 1.0 if "BULL" in direction else 0.0,
            "bearish_direction": 1.0 if "BEAR" in direction else 0.0,
            "accumulation_setup": 1.0 if "ACCUM" in category else 0.0,
            "distribution_setup": 1.0 if "DISTRIB" in category else 0.0,
            "breakout_setup": 1.0 if any(x in category for x in ("BREAKOUT", "BREAKDOWN")) else 0.0,
            "mean_reversion_setup": 1.0 if "MEAN_REVERSION" in category else 0.0,
            "uptrend_regime": 1.0 if "UPTREND" in regime or "BULL" in regime else 0.0,
            "downtrend_regime": 1.0 if "DOWNTREND" in regime or "BEAR" in regime else 0.0,
            "negative_gamma_regime": 1.0 if "NEGATIVE" in gamma else 0.0,
        }
        features = {name: round(_number(raw.get(name)), 8) for name in NUMERIC_FEATURES}
        forbidden = [name for name in features if any(token in name.lower() for token in FORBIDDEN_FEATURE_TOKENS)]
        if forbidden:
            raise RuntimeError(f"Point-in-time feature leakage detected: {forbidden}")
        return features

    @staticmethod
    def lineage(candidate: Any) -> dict[str, Any]:
        payload = _dict(candidate)
        metadata = _dict(payload.get("metadata"))
        return {
            "feature_version": PointInTimeFeatureBuilder.version,
            "scanner_run_id": metadata.get("scanner_run_id"),
            "candidate_state_hash": payload.get("state_hash"),
            "snapshot_timestamp": payload.get("snapshot_timestamp"),
            "source_provider": payload.get("provider"),
            "feature_allow_list": list(NUMERIC_FEATURES),
            "future_fields_excluded": True,
        }
