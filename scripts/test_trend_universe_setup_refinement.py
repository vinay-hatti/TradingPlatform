from __future__ import annotations

from trading_ai.market.trend_universe import (
    PrimaryTrendSetup,
    TrendUniverseType,
    _qualifies,
    classify_primary_setup,
    eligible_trend_universes,
)


def row(short: str, intermediate: str, long: str, **overrides):
    value = {
        "symbol": "TEST",
        "short_term_state": short,
        "intermediate_term_state": intermediate,
        "long_term_state": long,
        "trend_stage": "ESTABLISHED_TREND",
        "alignment_score": 90.0,
        "trend_quality_score": 90.0,
        "trend_confidence": 90.0,
        "relative_strength_vs_spy": 1.0,
        "relative_strength_vs_sector": 1.0,
        "transition_direction": "BULLISH",
        "exhaustion_risk_score": 25.0,
    }
    value.update(overrides)
    return value


def main() -> None:
    mature_bull = row("STRONG_BULLISH", "STRONG_BULLISH", "STRONG_BULLISH")
    assert _qualifies(TrendUniverseType.STRONG_BULLISH_ALL.value, mature_bull)
    assert _qualifies(TrendUniverseType.BULLISH_ALIGNMENT.value, mature_bull)
    assert _qualifies(TrendUniverseType.BULLISH_CONTINUATION.value, mature_bull)
    assert not _qualifies(TrendUniverseType.EMERGING_BULLISH.value, mature_bull)
    assert classify_primary_setup(mature_bull) == PrimaryTrendSetup.STRONG_BULLISH_ALL

    emerging_bull = row(
        "STRONG_BULLISH",
        "BULLISH",
        "SIDEWAYS",
        trend_stage="EARLY_TREND",
    )
    assert _qualifies(TrendUniverseType.EMERGING_BULLISH.value, emerging_bull)
    assert not _qualifies(TrendUniverseType.BULLISH_ALIGNMENT.value, emerging_bull)
    assert classify_primary_setup(emerging_bull) == PrimaryTrendSetup.EMERGING_BULLISH

    adverse_transition = row(
        "BULLISH",
        "STRONG_BULLISH",
        "STRONG_BULLISH",
        transition_direction="BEARISH",
    )
    assert not _qualifies(TrendUniverseType.BULLISH_CONTINUATION.value, adverse_transition)

    exhausted = row(
        "BULLISH",
        "STRONG_BULLISH",
        "STRONG_BULLISH",
        exhaustion_risk_score=75.0,
    )
    assert not _qualifies(TrendUniverseType.BULLISH_CONTINUATION.value, exhausted)

    mature_bear = row(
        "STRONG_BEARISH",
        "STRONG_BEARISH",
        "STRONG_BEARISH",
        relative_strength_vs_spy=-1.0,
        relative_strength_vs_sector=-1.0,
        transition_direction="BEARISH",
    )
    assert _qualifies(TrendUniverseType.STRONG_BEARISH_ALL.value, mature_bear)
    assert _qualifies(TrendUniverseType.BEARISH_ALIGNMENT.value, mature_bear)
    assert _qualifies(TrendUniverseType.BEARISH_CONTINUATION.value, mature_bear)
    assert not _qualifies(TrendUniverseType.EMERGING_BEARISH.value, mature_bear)
    assert classify_primary_setup(mature_bear) == PrimaryTrendSetup.STRONG_BEARISH_ALL

    memberships = eligible_trend_universes(mature_bull)
    assert TrendUniverseType.STRONG_BULLISH_ALL.value in memberships
    assert TrendUniverseType.BULLISH_ALIGNMENT.value in memberships
    assert TrendUniverseType.BULLISH_CONTINUATION.value in memberships
    assert TrendUniverseType.EMERGING_BULLISH.value not in memberships

    print("Trend universe setup refinement assertions passed.")


if __name__ == "__main__":
    main()
