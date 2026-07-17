from datetime import date, timedelta
import json

from trading_ai.strategy_engine.adaptive_strategy_engine import AdaptiveStrategyEngine
from trading_ai.strategy_engine.strategy_learning_policy import StrategyLearningPolicy
from trading_ai.strategy_engine.strategy_learning_serialization import strategy_learning_to_json
from trading_ai.strategy_engine.strategy_learning_service import StrategyLearningService


def outcomes(strategy, count, base_return, regime="TREND_UP", volatility="NORMAL", start=None):
    start = start or date(2026, 6, 30)
    rows = []
    for index in range(count):
        realized = base_return if index % 5 != 0 else -abs(base_return) * 0.5
        rows.append({
            "strategy": strategy,
            "outcome_date": (start - timedelta(days=index * 2)).isoformat(),
            "realized_return": realized,
            "pnl": realized * 1000.0,
            "symbol": "AAPL",
            "direction": "BULLISH",
            "market_regime": regime,
            "volatility_regime": volatility,
            "calibration_score": 82.0,
            "execution_score": 78.0,
        })
    return rows


def main():
    policy = StrategyLearningPolicy(
        minimum_observations=20,
        minimum_segment_observations=10,
        base_prior_weight=0.25,
        performance_weight=0.60,
        stability_weight=0.05,
        recency_weight=0.10,
        maximum_weight=1.0,
    )
    service = StrategyLearningService(policy)
    data = outcomes("LONG_CALL", 40, 0.04) + outcomes("BULL_CALL_SPREAD", 40, 0.02)
    profiles = service.learn(data, as_of_date=date(2026, 7, 1))

    assert set(profiles) == {"LONG_CALL", "BULL_CALL_SPREAD"}
    assert profiles["LONG_CALL"].valid
    assert profiles["LONG_CALL"].allowed
    assert profiles["LONG_CALL"].performance_score > profiles["BULL_CALL_SPREAD"].performance_score
    assert profiles["LONG_CALL"].effective_sample_size > 10.0
    assert any(segment.segment_key == "market_regime" for segment in profiles["LONG_CALL"].segments)

    weighting = service.build_dynamic_weights(profiles, prior_weights={"LONG_CALL": 0.5, "BULL_CALL_SPREAD": 0.5})
    assert weighting.valid and weighting.allowed
    assert abs(weighting.total_weight - 1.0) < 1e-5
    assert weighting.weights[0].strategy == "LONG_CALL"
    assert weighting.effective_strategy_count > 1.0

    adaptive_profiles = service.to_adaptive_performance_profiles(profiles)
    candidates = [
        {"symbol": "AAPL", "strategy": "LONG_CALL", "direction": "BULLISH", "market_regime": "TREND_UP", "volatility_regime": "NORMAL", "score": 70.0},
        {"symbol": "AAPL", "strategy": "BULL_CALL_SPREAD", "direction": "BULLISH", "market_regime": "TREND_UP", "volatility_regime": "NORMAL", "score": 70.0},
    ]
    selection = AdaptiveStrategyEngine().select("AAPL", candidates, adaptive_profiles)
    assert selection.valid
    assert selection.selected_strategy == "LONG_CALL"

    payload = json.loads(strategy_learning_to_json({"profiles": profiles, "weighting": weighting}))
    assert payload["profiles"]["LONG_CALL"]["strategy"] == "LONG_CALL"
    assert len(payload["weighting"]["weights"]) == 2

    insufficient = service.learn(outcomes("IRON_CONDOR", 5, 0.01), as_of_date=date(2026, 7, 1))["IRON_CONDOR"]
    assert not insufficient.valid
    assert "STRATEGY_LEARNING_NOT_GOVERNANCE_READY" in insufficient.rejection_reasons

    print("All strategy-learning and dynamic-weighting assertions passed.")


if __name__ == "__main__":
    main()
