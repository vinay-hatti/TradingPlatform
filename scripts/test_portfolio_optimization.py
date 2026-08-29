import json

from trading_ai.strategy_engine.portfolio_optimization_policy import PortfolioOptimizationPolicy
from trading_ai.strategy_engine.portfolio_optimization_serialization import portfolio_optimization_to_dict
from trading_ai.strategy_engine.portfolio_optimization_service import PortfolioOptimizationService


def build_candidates():
    return [
        {"decision_id": "AAPL_1", "symbol": "AAPL", "strategy": "BULL_CALL_SPREAD", "sector": "TECHNOLOGY", "correlation_group": "MEGA_CAP_TECH", "capital_required": 5000.0, "maximum_loss": 2500.0, "expected_profit": 900.0, "expected_return_pct": 0.18, "ranking_score": 92.0, "strategy_score": 88.0, "surface_score": 84.0, "surface_severity": "LOW", "allowed": True, "net_delta": 35.0, "net_gamma": 1.2, "net_theta": -18.0, "net_vega": 45.0},
        {"decision_id": "MSFT_1", "symbol": "MSFT", "strategy": "BULL_PUT_SPREAD", "sector": "TECHNOLOGY", "correlation_group": "MEGA_CAP_TECH", "capital_required": 4000.0, "maximum_loss": 1800.0, "expected_profit": 720.0, "expected_return_pct": 0.18, "ranking_score": 89.0, "strategy_score": 86.0, "surface_score": 80.0, "surface_severity": "MODERATE", "allowed": True, "net_delta": 28.0, "net_gamma": 0.9, "net_theta": 22.0, "net_vega": -35.0},
        {"decision_id": "JPM_1", "symbol": "JPM", "strategy": "BEAR_CALL_SPREAD", "sector": "FINANCIALS", "correlation_group": "BANKS", "capital_required": 3000.0, "maximum_loss": 1400.0, "expected_profit": 540.0, "expected_return_pct": 0.18, "ranking_score": 85.0, "strategy_score": 82.0, "surface_score": 78.0, "surface_severity": "LOW", "allowed": True, "net_delta": -24.0, "net_gamma": -0.6, "net_theta": 16.0, "net_vega": -20.0},
        {"decision_id": "BAD_1", "symbol": "BAD", "strategy": "SHORT_STRADDLE", "sector": "UNKNOWN", "correlation_group": "UNKNOWN", "capital_required": 10000.0, "maximum_loss": 9000.0, "expected_profit": 500.0, "expected_return_pct": 0.05, "ranking_score": 70.0, "strategy_score": 65.0, "surface_score": 20.0, "surface_severity": "CRITICAL", "allowed": True},
    ]


def main():
    policy = PortfolioOptimizationPolicy(
        maximum_portfolio_exposure_pct=0.30,
        maximum_total_risk_pct=0.12,
        maximum_position_weight_pct=0.12,
        maximum_sector_weight_pct=0.20,
        maximum_correlation_group_weight_pct=0.18,
        maximum_positions=4,
        allocation_step_pct=0.01,
    )
    service = PortfolioOptimizationService(policy=policy)
    profile = service.optimize(build_candidates(), initial_capital=100000.0)

    print("\n========== PORTFOLIO OPTIMIZATION ==========")
    print(f"Selected              : {profile.selected_count}")
    print(f"Allocated             : ${profile.total_allocated_capital:,.2f}")
    print(f"Exposure              : {profile.portfolio_exposure_pct:.2%}")
    print(f"Maximum Risk          : ${profile.total_maximum_loss:,.2f}")
    print(f"Expected Profit       : ${profile.expected_portfolio_profit:,.2f}")
    print(f"Objective Score       : {profile.objective_score:.2f}")
    print(f"Grade                 : {profile.optimization_grade}")
    print(f"Allowed               : {profile.allowed}")

    assert profile.valid is True
    assert profile.allowed is True
    assert profile.selected_count >= 2
    assert profile.total_allocated_capital <= 30000.0 + 1e-9
    assert profile.total_maximum_loss <= 12000.0 + 1e-9
    assert profile.portfolio_exposure_pct <= 0.30 + 1e-9
    assert all(item.allocation_weight_pct <= 0.12 + 1e-9 for item in profile.allocations)
    assert any(item.get("candidate_id") == "BAD_1" for item in profile.rejected_candidates)
    assert 0.0 <= profile.objective_score <= 100.0
    assert profile.optimization_grade in {"A", "B", "C", "D", "F"}
    payload = portfolio_optimization_to_dict(profile)
    json.dumps(payload)
    assert payload["allocations"]

    invalid = service.optimize([], initial_capital=100000.0)
    assert invalid.valid is False
    assert invalid.allowed is False
    assert invalid.rejection_reasons

    print("All portfolio-optimization assertions passed.")


if __name__ == "__main__":
    main()
