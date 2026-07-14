from trading_ai.strategy_engine.risk_surface_policy import RiskSurfacePolicy
from trading_ai.strategy_engine.risk_surface_serialization import risk_surface_to_dict
from trading_ai.strategy_engine.risk_surface_service import RiskSurfaceService


def main():
    policy = RiskSurfacePolicy(
        price_shocks_pct=(-0.10, 0.0, 0.10),
        volatility_shocks=(-0.10, 0.0, 0.10),
        time_offsets_days=(0, 5, 15),
        maximum_loss_pct_of_capital=0.08,
    )
    service = RiskSurfaceService(policy=policy)

    defined_risk = service.analyze_strategy(
        symbol="AAPL", strategy="BULL_CALL_SPREAD", underlying_price=200.0,
        implied_volatility=0.35, days_to_expiration=30, capital_required=3000.0,
        initial_capital=100000.0, net_delta=0.20, net_gamma=0.002,
        net_vega=20.0, net_theta=-5.0, net_rho=2.0,
    )
    short_gamma = service.analyze_strategy(
        symbol="SPX", strategy="SHORT_STRADDLE", underlying_price=6000.0,
        implied_volatility=0.22, days_to_expiration=20, capital_required=25000.0,
        initial_capital=100000.0, net_delta=0.0, net_gamma=-0.02,
        net_vega=-250.0, net_theta=80.0, net_rho=5.0,
    )

    assert defined_risk.valid is True
    assert defined_risk.point_count == 27
    assert defined_risk.worst_case_pnl <= defined_risk.best_case_pnl
    assert 0.0 <= defined_risk.surface_score <= 100.0
    assert len(defined_risk.attributions) == 5

    assert short_gamma.valid is True
    assert short_gamma.worst_case_pnl < defined_risk.worst_case_pnl
    assert short_gamma.risk_severity in {"MODERATE", "SEVERE", "CRITICAL"}

    serialized = risk_surface_to_dict(defined_risk)
    assert serialized["symbol"] == "AAPL"
    assert len(serialized["points"]) == 27

    portfolio = service.analyze_portfolio(
        profiles=[defined_risk, short_gamma], initial_capital=100000.0
    )
    assert portfolio.valid is True
    assert portfolio.position_count == 2
    assert portfolio.point_count == 27
    assert portfolio.largest_loss_contributor in {"AAPL", "SPX"}

    print("All risk-surface assertions passed.")


if __name__ == "__main__":
    main()
