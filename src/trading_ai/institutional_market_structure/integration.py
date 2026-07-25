from __future__ import annotations


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def scanner_context(snapshot, option_type: str, strategy_family: str = "LONG_PREMIUM") -> dict:
    """Translate a persisted market-structure snapshot into strategy-aware scanner context.

    Snapshot probabilities are expressed on a 0-100 scale. The returned score
    adjustment is intentionally bounded and remains an enrichment, never a hard gate.
    """
    right = option_type.upper()
    bullish = right in {"CALL", "C"}
    long_premium = strategy_family.upper() in {"LONG_PREMIUM", "LONG_CALL", "LONG_PUT"}

    alignment = float(snapshot.bull_probability if bullish else snapshot.bear_probability)
    directional_break = float(snapshot.breakout_probability if bullish else snapshot.breakdown_probability)
    directional_wall = snapshot.primary_call_wall if bullish else snapshot.primary_put_wall
    wall_distance = None
    if directional_wall is not None and snapshot.spot:
        wall_distance = (float(directional_wall) - float(snapshot.spot)) / float(snapshot.spot) * 100.0

    adjustment = (alignment - 50.0) * 0.12
    adjustment += (directional_break - 50.0) * 0.05

    pressure = float(snapshot.dealer_hedging_pressure)
    adjustment += (pressure if bullish else -pressure) * 0.025

    gamma_regime = str(snapshot.gamma_regime or "").upper()
    if snapshot.gamma_flip_distance_pct is not None:
        above_flip = float(snapshot.gamma_flip_distance_pct) >= 0
        adjustment += 1.25 if above_flip == bullish else -1.25

    # Nearby directional walls cap long-premium upside/downside continuation.
    if wall_distance is not None:
        signed_distance = wall_distance if bullish else -wall_distance
        if 0 <= signed_distance <= 1.0:
            adjustment -= 3.0
        elif 1.0 < signed_distance <= 2.5:
            adjustment -= 1.5

    range_probability = float(snapshot.range_probability)
    vol_expansion = float(snapshot.volatility_expansion_probability)
    if long_premium:
        adjustment -= max(0.0, range_probability - 50.0) * 0.08
        adjustment += max(0.0, vol_expansion - 50.0) * 0.05
        if "POSITIVE" in gamma_regime:
            adjustment -= 1.0
    else:
        adjustment += max(0.0, range_probability - 50.0) * 0.05
        if "POSITIVE" in gamma_regime:
            adjustment += 0.75

    adjustment *= _clamp(float(snapshot.confidence_score), 0.0, 1.0)
    adjustment = _clamp(adjustment, -15.0, 15.0)

    return {
        "market_structure_snapshot_date": snapshot.option_snapshot_date,
        "institutional_positioning_score": snapshot.institutional_positioning_score,
        "positioning_label": snapshot.positioning_label,
        "gamma_regime": snapshot.gamma_regime,
        "spot_vs_gamma_flip_pct": snapshot.gamma_flip_distance_pct,
        "distance_to_directional_wall_pct": wall_distance,
        "dealer_hedging_pressure": snapshot.dealer_hedging_pressure,
        "range_probability": snapshot.range_probability,
        "breakout_probability": snapshot.breakout_probability,
        "breakdown_probability": snapshot.breakdown_probability,
        "volatility_expansion_probability": snapshot.volatility_expansion_probability,
        "market_structure_confidence": snapshot.confidence_score,
        "directional_alignment_probability": alignment,
        "scanner_score_adjustment": adjustment,
    }
