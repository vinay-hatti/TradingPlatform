from dataclasses import dataclass

from trading_ai.strategy_engine.adaptive_strategy_engine import AdaptiveStrategyEngine
from trading_ai.strategy_engine.adaptive_strategy_integration import attach_adaptive_strategy_profile
from trading_ai.strategy_engine.adaptive_strategy_policy import AdaptiveStrategyPolicy
from trading_ai.strategy_engine.adaptive_strategy_serialization import adaptive_strategy_to_dict


@dataclass
class Candidate:
    symbol: str
    strategy: str
    direction: str
    market_regime: str
    volatility_regime: str
    score: float


def main():
    candidates = [
        Candidate("AAPL", "LONG_CALL", "CALL", "BULL_TREND", "NORMAL_VOL", 78.0),
        Candidate("AAPL", "BULL_CALL_SPREAD", "CALL", "BULL_TREND", "NORMAL_VOL", 75.0),
        Candidate("AAPL", "SHORT_PUT", "CALL", "BULL_TREND", "HIGH_VOL", 73.0),
    ]
    history = {
        "LONG_CALL": {"observation_count": 80, "win_rate": 0.61, "average_return": 0.12, "profit_factor": 1.55, "maximum_drawdown_pct": 0.11, "sharpe_ratio": 1.2, "calibration_score": 82, "execution_score": 76, "context_observation_count": 34, "context_win_rate": 0.68, "context_average_return": 0.15},
        "BULL_CALL_SPREAD": {"observation_count": 100, "win_rate": 0.66, "average_return": 0.10, "profit_factor": 1.70, "maximum_drawdown_pct": 0.08, "sharpe_ratio": 1.4, "calibration_score": 86, "execution_score": 88, "context_observation_count": 42, "context_win_rate": 0.72, "context_average_return": 0.13},
        "SHORT_PUT": {"observation_count": 60, "win_rate": 0.25, "average_return": -0.08, "profit_factor": 0.55, "maximum_drawdown_pct": 0.29, "sharpe_ratio": -0.4, "calibration_score": 48, "execution_score": 62, "context_observation_count": 20, "context_win_rate": 0.20, "context_average_return": -0.10},
    }
    engine = AdaptiveStrategyEngine(AdaptiveStrategyPolicy())
    profile = engine.select("AAPL", candidates, history)
    assert profile.valid and profile.allowed
    assert profile.selected_strategy == "BULL_CALL_SPREAD"
    assert len(profile.candidates) == 3
    short_put = next(item for item in profile.candidates if item.strategy == "SHORT_PUT")
    assert not short_put.allowed
    assert "SEVERE_STRATEGY_DRAWDOWN" in short_put.rejection_reasons
    payload = adaptive_strategy_to_dict(profile)
    assert payload["selected_strategy"] == "BULL_CALL_SPREAD"
    target = {"metadata": {}}
    attach_adaptive_strategy_profile(target, profile)
    assert target["adaptive_strategy_profile"] is profile
    assert target["metadata"]["adaptive_strategy_profile"]["valid"] is True

    fallback = engine.select("MSFT", [Candidate("MSFT", "LONG_CALL", "CALL", "BULL_TREND", "LOW_VOL", 80)], {})
    assert fallback.valid
    assert fallback.selected_strategy is None
    assert fallback.recommendation == "FALLBACK_TO_RULE_BASED_SELECTION"
    print("All adaptive-strategy foundation assertions passed.")


if __name__ == "__main__":
    main()
