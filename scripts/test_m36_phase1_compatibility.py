from trading_ai.portfolio_management.adapter import strategy_position_payload
from trading_ai.strategy_engine.portfolio_position import PortfolioPosition


def main() -> None:
    position = PortfolioPosition(
        symbol="MSFT", strategy="BULL_CALL_SPREAD", direction="CALL",
        contracts=2, capital_required=800.0, maximum_loss=800.0,
        expected_profit=400.0, expected_return_pct=0.5,
        allocation_pct=0.008, risk_pct=0.008,
        delta=20.0, gamma=0.1, theta=-4.0, vega=12.0, rho=1.0,
        sector="TECHNOLOGY", industry="SOFTWARE",
        correlation_group="MEGA_CAP_TECH", ranking_score=90.0,
        strategy_score=88.0, portfolio_fit_score=85.0,
        readiness="LIVE_CANDIDATE", action="APPROVE",
        metadata={"strategy_id": "MSFT:TEST"},
    )
    payload = strategy_position_payload(position)
    assert payload["strategy_id"] == "MSFT:TEST"
    assert payload["capital_committed"] == 800.0
    assert payload["entry_price"] == 4.0
    print("Milestone 36 Phase 1 compatibility assertions passed.")


if __name__ == "__main__":
    main()
