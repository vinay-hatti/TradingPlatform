import json

import numpy as np
import pandas as pd

from trading_ai.strategy_engine.market_regime_policy import (
    MarketRegimePolicy,
)
from trading_ai.strategy_engine.market_regime_serialization import (
    market_regime_to_dict,
)
from trading_ai.strategy_engine.market_regime_service import (
    MarketRegimeService,
)


def build_trend(start, drift, volatility, count=260, seed=42):
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, volatility, count)
    close = start * np.exp(np.cumsum(returns))
    return pd.DataFrame({"close": close})


def build_stress(count=260):
    rng = np.random.default_rng(7)
    first = rng.normal(0.0005, 0.008, count - 45)
    crash = rng.normal(-0.010, 0.035, 45)
    close = 200.0 * np.exp(np.cumsum(np.concatenate([first, crash])))
    return pd.DataFrame({"close": close})


def main():
    service = MarketRegimeService(
        policy=MarketRegimePolicy(
            minimum_observations=120,
            reject_critical_regime=False,
        )
    )
    trend_service = MarketRegimeService(
        policy=MarketRegimePolicy(
            minimum_observations=120,
            stress_drawdown_threshold=-0.60,
            stress_volatility_threshold=0.80,
        )
    )

    bull = trend_service.analyze(
        build_trend(100.0, 0.0018, 0.004, seed=1),
        symbol="BULL",
    )
    bear = trend_service.analyze(
        build_trend(200.0, -0.0018, 0.004, seed=2),
        symbol="BEAR",
    )
    stress = service.analyze(build_stress(), symbol="STRESS")
    insufficient = service.analyze([100.0, 101.0, 102.0], symbol="SHORT")

    print("\n========== MARKET REGIME ANALYTICS ==========")
    for profile in (bull, bear, stress):
        print(
            f"{profile.symbol:<8} "
            f"Regime={profile.current_regime:<20} "
            f"Score={profile.regime_score:>6.2f} "
            f"Confidence={profile.confidence_score:>6.2f} "
            f"Severity={profile.regime_severity}"
        )

    assert bull.valid is True
    assert bull.allowed is True
    assert bull.current_regime in {
        "STRONG_BULL_TREND",
        "BULL_TREND",
    }
    assert bull.short_return > 0.0
    assert 0.0 <= bull.regime_score <= 100.0
    assert 0.0 <= bull.confidence_score <= 100.0

    assert bear.valid is True
    assert bear.current_regime in {
        "STRONG_BEAR_TREND",
        "BEAR_TREND",
    }
    assert bear.short_return < 0.0

    assert stress.valid is True
    assert stress.current_regime in {
        "STRESS",
        "STRONG_BEAR_TREND",
        "HIGH_VOLATILITY",
    }
    assert stress.regime_severity in {
        "MODERATE",
        "SEVERE",
        "CRITICAL",
    }
    assert stress.current_drawdown <= 0.0

    assert insufficient.valid is False
    assert "INSUFFICIENT_REGIME_OBSERVATIONS" in insufficient.warnings

    many = service.analyze_many({
        "BULL": build_trend(100.0, 0.0018, 0.004, seed=3),
        "BEAR": build_trend(100.0, -0.0018, 0.004, seed=4),
    })
    assert set(many) == {"BULL", "BEAR"}

    payload = market_regime_to_dict(bull)
    encoded = json.dumps(payload)
    assert "current_regime" in encoded
    assert isinstance(payload["transitions"], list)
    assert isinstance(payload["metadata"], dict)

    print("\nAll market-regime assertions passed.")


if __name__ == "__main__":
    main()
