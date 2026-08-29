from trading_ai.risk_gateway.portfolio_risk_policy import PortfolioRiskPolicy
from trading_ai.risk_gateway.portfolio_risk_profile import (
    PortfolioPositionProfile, PortfolioSnapshotProfile, PositionLimitProfile,
)
from trading_ai.risk_gateway.portfolio_risk_serialization import dumps
from trading_ai.risk_gateway.portfolio_risk_service import PortfolioRiskService
from trading_ai.risk_gateway.pretrade_risk_profile import (
    PreTradeAccountProfile, PreTradeRiskLeg, PreTradeRiskRequest,
)

def main():
    account = PreTradeAccountProfile(
        account_id="PAPER-001", currency="USD",
        net_liquidation=200000.0, buying_power=300000.0,
        option_buying_power=150000.0, cash_balance=100000.0,
        excess_liquidity=150000.0,
    )
    positions = (
        PortfolioPositionProfile(
            account_id="PAPER-001", symbol="AAPL", underlying_symbol="AAPL",
            asset_class="EQUITY", sector="TECHNOLOGY", quantity=100,
            average_cost=180.0, market_price=200.0, multiplier=1,
            buying_power_usage=20000.0,
        ),
        PortfolioPositionProfile(
            account_id="PAPER-001", symbol="MSFT", underlying_symbol="MSFT",
            asset_class="EQUITY", sector="TECHNOLOGY", quantity=50,
            average_cost=380.0, market_price=400.0, multiplier=1,
            buying_power_usage=20000.0,
        ),
    )
    snapshot = PortfolioSnapshotProfile(
        account=account,
        positions=positions,
        position_limits=(
            PositionLimitProfile(
                symbol="AAPL", asset_class="EQUITY",
                maximum_absolute_quantity=500,
                maximum_notional=100000.0,
            ),
        ),
    )

    service = PortfolioRiskService()
    approved_order = PreTradeRiskRequest(
        aggregate_id="agg-portfolio-001", client_order_id="client-portfolio-001",
        account_id="PAPER-001", order_type="LIMIT", time_in_force="DAY",
        legs=(
            PreTradeRiskLeg(
                leg_id="leg-1", symbol="AAPL", asset_class="EQUITY",
                side="BUY", quantity=25, price=200.0, multiplier=1,
                metadata={"sector": "TECHNOLOGY"},
            ),
        ),
    )
    approved = service.evaluate(approved_order, snapshot)
    assert approved.allowed
    assert approved.exposure is not None
    assert approved.exposure.current_gross_exposure == 40000.0
    assert approved.exposure.projected_gross_exposure == 45000.0
    assert approved.exposure.projected_open_positions == 2
    assert approved.exposure.new_positions == 0
    aapl = next(x for x in approved.exposure.symbols if x.symbol == "AAPL")
    assert aapl.projected_quantity == 125
    assert aapl.projected_exposure == 25000.0

    concentration_service = PortfolioRiskService(PortfolioRiskPolicy(
        maximum_single_symbol_exposure=30000.0,
        maximum_single_symbol_pct_of_net_liquidation=0.15,
        maximum_sector_exposure=60000.0,
        maximum_sector_pct_of_net_liquidation=0.30,
    ))
    concentrated = concentration_service.evaluate(
        PreTradeRiskRequest(
            aggregate_id="agg-portfolio-002", client_order_id="client-portfolio-002",
            account_id="PAPER-001", order_type="LIMIT", time_in_force="DAY",
            legs=(
                PreTradeRiskLeg(
                    leg_id="leg-1", symbol="AAPL", asset_class="EQUITY",
                    side="BUY", quantity=100, price=200.0, multiplier=1,
                    metadata={"sector": "TECHNOLOGY"},
                ),
            ),
        ),
        snapshot,
    )
    assert not concentrated.allowed
    assert "SINGLE_SYMBOL_EXPOSURE:AAPL" in concentrated.rejection_reasons
    assert "SINGLE_SYMBOL_CONCENTRATION:AAPL" in concentrated.rejection_reasons

    position_limited = service.evaluate(
        PreTradeRiskRequest(
            aggregate_id="agg-portfolio-003", client_order_id="client-portfolio-003",
            account_id="PAPER-001", order_type="LIMIT", time_in_force="DAY",
            legs=(
                PreTradeRiskLeg(
                    leg_id="leg-1", symbol="AAPL", asset_class="EQUITY",
                    side="BUY", quantity=450, price=200.0, multiplier=1,
                    metadata={"sector": "TECHNOLOGY"},
                ),
            ),
        ),
        snapshot,
    )
    assert not position_limited.allowed
    assert "POSITION_ABSOLUTE_LIMIT:AAPL" in position_limited.rejection_reasons
    assert "POSITION_NOTIONAL_LIMIT:AAPL" in position_limited.rejection_reasons

    bp_service = PortfolioRiskService(PortfolioRiskPolicy(
        maximum_total_buying_power_utilization=0.20,
    ))
    bp_rejected = bp_service.evaluate(
        PreTradeRiskRequest(
            aggregate_id="agg-portfolio-004", client_order_id="client-portfolio-004",
            account_id="PAPER-001", order_type="LIMIT", time_in_force="DAY",
            legs=(
                PreTradeRiskLeg(
                    leg_id="leg-1", symbol="NVDA", asset_class="EQUITY",
                    side="BUY", quantity=200, price=150.0, multiplier=1,
                    metadata={"sector": "TECHNOLOGY"},
                ),
            ),
        ),
        snapshot,
    )
    assert not bp_rejected.allowed
    assert "BUYING_POWER_UTILIZATION" in bp_rejected.rejection_reasons

    mismatch = service.evaluate(
        PreTradeRiskRequest(
            aggregate_id="agg-portfolio-005", client_order_id="client-portfolio-005",
            account_id="OTHER-ACCOUNT", order_type="LIMIT", time_in_force="DAY",
            legs=approved_order.legs,
        ),
        snapshot,
    )
    assert not mismatch.allowed
    assert "ACCOUNT_MATCH" in mismatch.rejection_reasons

    payload = dumps(approved)
    assert '"projected_gross_exposure": 45000.0' in payload
    assert '"recommendation": "APPROVE"' in payload
    print("All portfolio exposure, concentration, buying-power, and position-limit risk-control assertions passed.")

if __name__ == "__main__":
    main()
