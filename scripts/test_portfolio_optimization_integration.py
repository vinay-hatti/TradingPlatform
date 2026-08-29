from types import SimpleNamespace

from trading_ai.strategy_engine.portfolio_optimization_service import PortfolioOptimizationService
from trading_ai.strategy_engine.portfolio_optimization_policy import PortfolioOptimizationPolicy


def decision(i, symbol, sector, corr, score, surface, capital, loss, profit):
    return SimpleNamespace(
        decision_id=f"D{i}", symbol=symbol, strategy="BULL_PUT_SPREAD",
        sector=sector, correlation_group=corr, capital_required=capital,
        maximum_loss=loss, expected_profit=profit,
        expected_return_pct=profit/capital, ranking_score=score,
        strategy_score=score-2, allowed=True, net_delta=10.0,
        net_gamma=0.2, net_theta=5.0, net_vega=-15.0, net_rho=2.0,
        risk_surface_profile=SimpleNamespace(
            valid=True, allowed=True, surface_score=surface, risk_severity="LOW"
        ), metadata={}, selected=False,
    )


def main():
    policy=PortfolioOptimizationPolicy(
        maximum_portfolio_exposure_pct=0.30, reserve_cash_pct=0.30,
        maximum_position_weight_pct=0.12, maximum_sector_weight_pct=0.20,
        maximum_correlation_group_weight_pct=0.20, allocation_step_pct=0.02,
    )
    service=PortfolioOptimizationService(policy=policy)
    decisions=[
        decision(1,"AAPL","TECH","MEGA_TECH",92,88,5000,3000,900),
        decision(2,"MSFT","TECH","MEGA_TECH",89,84,5000,3000,800),
        decision(3,"JPM","FINANCIALS","BANKS",86,82,4000,2400,650),
    ]
    profile=service.optimize(decisions,100000.0)
    assert profile.valid is True
    assert profile.allowed is True
    assert profile.selected_count >= 2
    assert profile.total_allocated_capital <= 30000.0 + 1e-9
    assert all(a.allocation_dollars > 0 for a in profile.allocations)
    assert len({a.candidate_id for a in profile.allocations}) == profile.selected_count
    serialized=__import__(
        "trading_ai.strategy_engine.portfolio_optimization_serialization",
        fromlist=["portfolio_optimization_to_dict"]
    ).portfolio_optimization_to_dict(profile)
    assert serialized["selected_count"] == profile.selected_count
    assert serialized["allocations"]
    print("All portfolio-optimization integration assertions passed.")

if __name__ == "__main__":
    main()
