import json

from trading_ai.strategy_engine.market_regime_forecast_policy import (
    MarketRegimeForecastPolicy,
)
from trading_ai.strategy_engine.market_regime_forecast_serialization import (
    market_regime_forecast_to_dict,
)
from trading_ai.strategy_engine.market_regime_forecast_service import (
    MarketRegimeForecastService,
)
from trading_ai.strategy_engine.market_regime_profile import MarketRegimeProfile


def main():
    persistent_history = (
        ["RANGE_BOUND"] * 20
        + ["BULL_TREND"] * 75
        + ["RANGE_BOUND"] * 5
        + ["BULL_TREND"] * 50
    )
    unstable_history = (
        ["BULL_TREND", "RANGE_BOUND", "BEAR_TREND", "TRANSITION"] * 35
    )
    stress_history = (
        ["HIGH_VOLATILITY"] * 20
        + ["STRESS"] * 85
    )

    service = MarketRegimeForecastService(
        MarketRegimeForecastPolicy(
            minimum_history_observations=30,
            minimum_transition_count=10,
            forecast_horizon=5,
        )
    )

    persistent = service.forecast(persistent_history, symbol="PERSISTENT")
    unstable = service.forecast(unstable_history, symbol="UNSTABLE")
    stress = service.forecast(stress_history, symbol="STRESS")

    source = MarketRegimeProfile(
        symbol="PROFILE",
        current_regime="BULL_TREND",
        regime_duration=40,
        regime_history=persistent_history,
        regime_score=82.0,
        confidence_score=88.0,
        valid=True,
    )
    from_profile = service.forecast_profile(source)

    for profile in (persistent, unstable, stress, from_profile):
        assert profile.valid is True
        assert 0.0 <= profile.forecast_probability <= 1.0
        assert 0.0 <= profile.persistence_probability <= 1.0
        assert 0.0 <= profile.transition_probability <= 1.0
        assert abs(sum(profile.next_regime_probabilities.values()) - 1.0) < 1e-9
        assert len(profile.horizon_forecasts) == 5
        assert 0.0 <= profile.forecast_score <= 100.0
        assert profile.forecast_grade in {"A", "B", "C", "D", "F"}

    assert persistent.current_regime == "BULL_TREND"
    assert persistent.persistence_probability > 0.80
    assert persistent.forecast_regime == "BULL_TREND"
    assert unstable.transition_probability > persistent.transition_probability
    assert "ELEVATED_REGIME_TRANSITION_RISK" in unstable.warnings
    assert stress.forecast_regime == "STRESS"
    assert stress.forecast_severity in {"SEVERE", "CRITICAL"}
    assert from_profile.metadata["source_regime_score"] == 82.0

    insufficient = service.forecast(["BULL_TREND"] * 10, symbol="SHORT")
    assert insufficient.valid is False
    assert "INSUFFICIENT_REGIME_HISTORY" in insufficient.warnings

    payload = market_regime_forecast_to_dict(persistent)
    json.dumps(payload)
    assert payload["forecast_regime"] == "BULL_TREND"

    print("\n========== REGIME FORECAST ANALYTICS ==========")
    for profile in (persistent, unstable, stress):
        print(
            f"{profile.symbol:<11} "
            f"Current={profile.current_regime:<16} "
            f"Forecast={profile.forecast_regime:<16} "
            f"Probability={profile.forecast_probability:.2%} "
            f"Persistence={profile.persistence_probability:.2%} "
            f"Score={profile.forecast_score:.2f}"
        )
    print("\nAll market-regime forecast assertions passed.")


if __name__ == "__main__":
    main()
