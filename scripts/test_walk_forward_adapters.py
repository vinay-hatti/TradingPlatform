from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_ai.strategy_engine.walk_forward_adapter_serialization import (
    walk_forward_adapter_to_dict,
)
from trading_ai.strategy_engine.walk_forward_backtest_adapter import (
    WalkForwardBacktestAdapter,
)
from trading_ai.strategy_engine.walk_forward_engine import (
    InstitutionalWalkForwardEngine,
)
from trading_ai.strategy_engine.walk_forward_policy import WalkForwardPolicy
from trading_ai.strategy_engine.walk_forward_portfolio_optimization_adapter import (
    WalkForwardPortfolioOptimizationAdapter,
)


@dataclass
class FakeTrade:
    pnl: float


def fake_backtest_runner(observations, parameters):
    threshold = float(parameters["threshold"])
    scale = float(parameters["scale"])
    trades = []
    for value in observations:
        pnl = (float(value) - threshold) * scale
        if abs(pnl) >= 0.05:
            trades.append(FakeTrade(pnl=pnl * 100.0))
    return {"trades": trades}


def build_candidate(index: int, quality: float) -> dict:
    return {
        "decision_id": f"D{index}",
        "symbol": ["AAPL", "MSFT", "JPM", "XOM"][index % 4],
        "strategy": ["BULL_PUT_SPREAD", "BULL_CALL_SPREAD"][index % 2],
        "sector": ["TECHNOLOGY", "FINANCIALS", "ENERGY"][index % 3],
        "correlation_group": ["GROWTH", "VALUE"][index % 2],
        "capital_required": 2000.0 + index * 100.0,
        "maximum_loss": 700.0 + index * 20.0,
        "expected_profit": 280.0 * quality,
        "expected_return_pct": 0.12 * quality,
        "ranking_score": 70.0 + quality * 20.0,
        "strategy_score": 68.0 + quality * 18.0,
        "surface_score": 72.0 + quality * 15.0,
        "surface_severity": "LOW",
        "allowed": True,
        "net_delta": 10.0,
        "net_gamma": 0.5,
        "net_theta": 5.0,
        "net_vega": 20.0,
        "net_rho": 2.0,
    }


def main():
    rng = np.random.default_rng(42)
    observations = list(rng.normal(0.55, 0.12, size=150))

    backtest_adapter = WalkForwardBacktestAdapter(
        fake_backtest_runner,
        initial_capital=100000.0,
        minimum_trades=2,
    )
    direct = backtest_adapter.evaluate_detailed(
        observations[:50],
        {"threshold": 0.50, "scale": 1.0},
    )
    assert direct.valid is True
    assert direct.trade_count >= 2
    assert 0.0 <= direct.max_drawdown_pct <= 1.0
    assert set(direct.as_engine_metrics()) == {
        "score", "return", "sharpe", "max_drawdown_pct"
    }

    policy = WalkForwardPolicy(
        train_size=50,
        validation_size=20,
        test_size=20,
        step_size=20,
        purge_size=2,
        embargo_size=2,
        minimum_windows=2,
        minimum_train_observations=40,
        minimum_validation_observations=15,
        minimum_test_observations=15,
        minimum_parameter_stability_score=0.0,
        maximum_oos_drawdown_pct=0.50,
    )
    profile = InstitutionalWalkForwardEngine(policy).run(
        observations,
        [
            {"threshold": 0.45, "scale": 0.8},
            {"threshold": 0.50, "scale": 1.0},
            {"threshold": 0.55, "scale": 1.2},
        ],
        backtest_adapter.evaluate,
    )
    assert profile.valid is True
    assert profile.completed_window_count >= 2
    assert backtest_adapter.diagnostics.evaluation_count > 0

    snapshots = []
    for snapshot_index in range(90):
        quality_shift = 0.80 + 0.002 * snapshot_index
        snapshots.append({
            "candidates": [
                build_candidate(index, quality_shift + index * 0.03)
                for index in range(6)
            ]
        })

    portfolio_adapter = WalkForwardPortfolioOptimizationAdapter(
        initial_capital=100000.0,
    )
    portfolio_result = portfolio_adapter.evaluate_detailed(
        snapshots[:20],
        {
            "maximum_portfolio_exposure_pct": 0.30,
            "maximum_total_risk_pct": 0.12,
            "maximum_sector_weight_pct": 0.25,
        },
    )
    assert portfolio_result.valid is True
    assert portfolio_result.metadata["snapshot_count"] == 20
    assert portfolio_result.trade_count > 0
    assert portfolio_result.score > 0.0

    portfolio_profile = InstitutionalWalkForwardEngine(
        WalkForwardPolicy(
            train_size=30,
            validation_size=15,
            test_size=15,
            step_size=15,
            purge_size=1,
            embargo_size=1,
            minimum_windows=2,
            minimum_train_observations=25,
            minimum_validation_observations=10,
            minimum_test_observations=10,
            minimum_parameter_stability_score=0.0,
            maximum_oos_drawdown_pct=0.50,
        )
    ).run(
        snapshots,
        [
            {
                "maximum_portfolio_exposure_pct": 0.25,
                "maximum_total_risk_pct": 0.10,
                "maximum_sector_weight_pct": 0.20,
            },
            {
                "maximum_portfolio_exposure_pct": 0.35,
                "maximum_total_risk_pct": 0.15,
                "maximum_sector_weight_pct": 0.30,
            },
        ],
        portfolio_adapter.evaluate,
    )
    assert portfolio_profile.valid is True
    assert portfolio_profile.completed_window_count >= 2
    assert portfolio_adapter.diagnostics.evaluation_count > 0

    payload = walk_forward_adapter_to_dict({
        "backtest": backtest_adapter.diagnostics,
        "portfolio": portfolio_adapter.diagnostics,
        "evaluation": portfolio_result,
    })
    json.dumps(payload)
    assert payload["evaluation"]["metadata"]["snapshot_count"] == 20

    try:
        portfolio_adapter.evaluate_detailed(
            snapshots[:5],
            {"unsupported_policy_field": 1.0},
        )
    except Exception:
        raise AssertionError("adapter must degrade safely instead of raising")

    print("All walk-forward adapter assertions passed.")


if __name__ == "__main__":
    main()
