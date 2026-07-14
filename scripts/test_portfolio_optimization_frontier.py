from types import SimpleNamespace

from trading_ai.strategy_engine.portfolio_optimization_frontier_policy import (
    PortfolioOptimizationFrontierPolicy,
)
from trading_ai.strategy_engine.portfolio_optimization_frontier_serialization import (
    portfolio_optimization_frontier_to_dict,
)
from trading_ai.strategy_engine.portfolio_optimization_frontier_service import (
    PortfolioOptimizationFrontierService,
)
from trading_ai.strategy_engine.portfolio_optimization_policy import (
    PortfolioOptimizationPolicy,
)


def candidate(
    decision_id,
    symbol,
    strategy,
    sector,
    group,
    capital,
    maximum_loss,
    expected_profit,
    ranking,
    strategy_score,
    surface_score,
    delta,
    gamma,
    theta,
    vega,
):
    return SimpleNamespace(
        decision_id=decision_id,
        symbol=symbol,
        strategy=strategy,
        sector=sector,
        correlation_group=group,
        capital_required=capital,
        maximum_loss=maximum_loss,
        expected_profit=expected_profit,
        expected_return_pct=expected_profit / capital,
        ranking_score=ranking,
        strategy_score=strategy_score,
        surface_score=surface_score,
        surface_severity="LOW",
        allowed=True,
        net_delta=delta,
        net_gamma=gamma,
        net_theta=theta,
        net_vega=vega,
        net_rho=0.0,
        metadata={},
    )


def main():
    candidates = [
        candidate("D1", "AAPL", "BULL_PUT_SPREAD", "TECHNOLOGY", "MEGA_CAP_TECH", 5000, 2200, 900, 92, 88, 86, 30, 0.8, 18, -120),
        candidate("D2", "MSFT", "BULL_CALL_SPREAD", "TECHNOLOGY", "MEGA_CAP_TECH", 6000, 2800, 1100, 89, 86, 82, 35, 1.0, -12, 150),
        candidate("D3", "JPM", "IRON_CONDOR", "FINANCIALS", "BANKS", 4000, 1600, 650, 84, 82, 78, 5, -0.4, 24, -90),
        candidate("D4", "XOM", "BEAR_CALL_SPREAD", "ENERGY", "ENERGY", 4500, 1900, 720, 81, 80, 75, -22, 0.6, 16, -80),
        candidate("D5", "GLD", "LONG_CALL", "COMMODITIES", "METALS", 3500, 3500, 900, 78, 76, 72, 25, 0.9, -8, 130),
    ]

    base_policy = PortfolioOptimizationPolicy(
        maximum_portfolio_exposure_pct=0.50,
        maximum_total_risk_pct=0.20,
        reserve_cash_pct=0.20,
        maximum_position_weight_pct=0.15,
        maximum_sector_weight_pct=0.35,
        maximum_strategy_weight_pct=0.40,
        maximum_correlation_group_weight_pct=0.30,
        maximum_positions=5,
        allocation_step_pct=0.02,
    )
    frontier_policy = PortfolioOptimizationFrontierPolicy(
        exposure_levels=(0.20, 0.30, 0.40, 0.50),
        risk_levels=(0.08, 0.12, 0.16),
        concentration_levels=(0.25, 0.35),
        maximum_points=24,
    )
    profile = PortfolioOptimizationFrontierService(
        base_policy=base_policy,
        frontier_policy=frontier_policy,
    ).analyze(candidates, 100000.0)

    print("\n========== PORTFOLIO OPTIMIZATION FRONTIER ==========")
    print(f"Points                 : {profile.point_count}")
    print(f"Valid Points           : {profile.valid_point_count}")
    print(f"Pareto Points          : {profile.pareto_point_count}")
    print(f"Best Point             : {profile.best_point_id}")
    print(f"Best Objective         : {profile.best_objective_score:.2f}")
    print(f"Selection Stability    : {profile.selection_stability_score:.2f}")
    print(f"Allocation Stability   : {profile.allocation_stability_score:.2f}")
    print(f"Constraint Sensitivity : {profile.constraint_sensitivity_score:.2f}")
    print(f"Frontier Score         : {profile.frontier_score:.2f}")
    print(f"Frontier Grade         : {profile.frontier_grade}")

    assert profile.valid is True
    assert profile.allowed is True
    assert profile.point_count == 24
    assert profile.valid_point_count >= frontier_policy.minimum_valid_points
    assert profile.pareto_point_count >= 1
    assert profile.best_point_id
    assert 0.0 <= profile.frontier_score <= 100.0
    assert profile.frontier_grade in {"A", "B", "C", "D", "F"}
    assert profile.risk_severity in {"LOW", "MODERATE", "SEVERE", "CRITICAL"}
    assert 0.0 <= profile.selection_stability_score <= 100.0
    assert 0.0 <= profile.allocation_stability_score <= 100.0
    assert 0.0 <= profile.constraint_sensitivity_score <= 100.0
    assert any(point.pareto_efficient for point in profile.points)
    assert all(point.expected_return_pct >= 0.0 for point in profile.pareto_points)

    payload = portfolio_optimization_frontier_to_dict(profile)
    assert payload["valid"] is True
    assert isinstance(payload["points"], list)
    assert isinstance(payload["pareto_points"], list)
    assert payload["best_point_id"] == profile.best_point_id

    invalid = PortfolioOptimizationFrontierService(
        base_policy=base_policy,
        frontier_policy=frontier_policy,
    ).analyze([], 100000.0)
    assert invalid.valid is False
    assert "NO_OPTIMIZATION_CANDIDATES" in invalid.rejection_reasons

    print("\nAll portfolio-optimization frontier assertions passed.")


if __name__ == "__main__":
    main()
