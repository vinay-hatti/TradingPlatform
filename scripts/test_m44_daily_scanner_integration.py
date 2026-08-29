from __future__ import annotations

from types import SimpleNamespace

from trading_ai.institutional_market_structure.integration import scanner_context


def snapshot(**overrides):
    values = dict(
        bull_probability=70.0,
        bear_probability=30.0,
        breakout_probability=65.0,
        breakdown_probability=35.0,
        primary_call_wall=105.0,
        primary_put_wall=95.0,
        spot=100.0,
        dealer_hedging_pressure=20.0,
        gamma_regime="POSITIVE_GAMMA",
        gamma_flip_distance_pct=2.0,
        range_probability=40.0,
        volatility_expansion_probability=60.0,
        confidence_score=0.80,
        option_snapshot_date="2026-07-24",
        institutional_positioning_score=75.0,
        positioning_label="MODERATELY_BULLISH",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def main() -> None:
    call = scanner_context(snapshot(), "CALL", "LONG_PREMIUM")
    put = scanner_context(snapshot(), "PUT", "LONG_PREMIUM")
    assert call["scanner_score_adjustment"] > 0
    assert put["scanner_score_adjustment"] < call["scanner_score_adjustment"]

    capped = scanner_context(
        snapshot(
            bull_probability=100.0,
            breakout_probability=100.0,
            dealer_hedging_pressure=100.0,
            confidence_score=1.0,
        ),
        "CALL",
        "LONG_PREMIUM",
    )
    assert -15.0 <= capped["scanner_score_adjustment"] <= 15.0
    print("Milestone 44 daily scanner dealer-positioning assertions passed.")


if __name__ == "__main__":
    main()
