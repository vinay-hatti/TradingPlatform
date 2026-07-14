import json
import math

import numpy as np

from trading_ai.strategy_engine.walk_forward_policy import WalkForwardPolicy
from trading_ai.strategy_engine.walk_forward_serialization import walk_forward_to_dict
from trading_ai.strategy_engine.walk_forward_service import InstitutionalWalkForwardService


def evaluator(observations, params):
    values = np.asarray(observations, dtype=float)
    signal = float(params["signal"])
    returns = values * signal
    total_return = float(np.prod(1.0 + returns) - 1.0)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * math.sqrt(252.0)) if std else 0.0
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    max_dd = abs(float(np.min(drawdown))) if len(drawdown) else 0.0
    score = 50.0 + total_return * 100.0 + sharpe * 5.0 - max_dd * 100.0
    return {
        "score": score,
        "return": total_return,
        "sharpe": sharpe,
        "max_drawdown_pct": max_dd,
    }


def main():
    rng = np.random.default_rng(42)
    observations = rng.normal(0.0008, 0.01, 900)
    policy = WalkForwardPolicy(
        train_size=252,
        validation_size=63,
        test_size=63,
        step_size=63,
        purge_size=3,
        embargo_size=3,
        minimum_windows=3,
        minimum_parameter_stability_score=20.0,
        maximum_oos_drawdown_pct=0.40,
    )
    profile = InstitutionalWalkForwardService(policy).validate(
        observations=observations,
        parameter_grid=[{"signal": 0.5}, {"signal": 1.0}, {"signal": 1.5}],
        evaluator=evaluator,
    )
    assert profile.valid is True
    assert profile.window_count >= 3
    assert profile.completed_window_count == len(profile.results)
    assert 0.0 <= profile.parameter_stability_score <= 100.0
    assert 0.0 <= profile.window_consistency_score <= 100.0
    assert 0.0 <= profile.walk_forward_score <= 100.0
    assert profile.walk_forward_grade in {"A", "B", "C", "D", "F"}
    assert profile.risk_severity in {"LOW", "MODERATE", "SEVERE", "CRITICAL"}
    for window in profile.windows:
        assert window.validation_start >= window.train_end + policy.purge_size
        assert window.test_start >= window.validation_end + policy.embargo_size
    payload = walk_forward_to_dict(profile)
    json.dumps(payload)
    print("Windows                :", profile.window_count)
    print("Completed              :", profile.completed_window_count)
    print("OOS Return             :", f"{profile.aggregate_oos_return:.2%}")
    print("Average OOS Sharpe     :", f"{profile.average_oos_sharpe:.2f}")
    print("Worst OOS Drawdown     :", f"{profile.worst_oos_drawdown_pct:.2%}")
    print("Parameter Stability    :", f"{profile.parameter_stability_score:.2f}")
    print("Walk-Forward Score     :", f"{profile.walk_forward_score:.2f}")
    print("Walk-Forward Grade     :", profile.walk_forward_grade)
    print("All institutional walk-forward assertions passed.")


if __name__ == "__main__":
    main()
