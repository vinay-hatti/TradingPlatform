from trading_ai.risk_gateway.options_risk_policy import OptionsRiskPolicy
from trading_ai.risk_gateway.options_risk_profile import (
    OptionGreekProfile, ScenarioShockProfile,
)
from trading_ai.risk_gateway.options_risk_serialization import dumps
from trading_ai.risk_gateway.options_risk_service import OptionsRiskService
from trading_ai.risk_gateway.pretrade_risk_profile import (
    PreTradeAccountProfile, PreTradeRiskLeg, PreTradeRiskRequest,
)

def main():
    account = PreTradeAccountProfile(
        account_id="PAPER-001",
        currency="USD",
        net_liquidation=200000.0,
        buying_power=300000.0,
        option_buying_power=150000.0,
        cash_balance=100000.0,
        excess_liquidity=150000.0,
    )

    spread_order = PreTradeRiskRequest(
        aggregate_id="agg-options-001",
        client_order_id="client-options-001",
        account_id="PAPER-001",
        order_type="LIMIT",
        time_in_force="DAY",
        strategy_name="BULL_CALL_SPREAD",
        legs=(
            PreTradeRiskLeg(
                leg_id="long-call",
                symbol="AAPL_200C",
                asset_class="OPTION",
                side="BUY_TO_OPEN",
                quantity=1,
                price=6.0,
                multiplier=100,
                strike=200.0,
                option_type="CALL",
                expiration="2026-08-21",
                metadata={"underlying_symbol": "AAPL"},
            ),
            PreTradeRiskLeg(
                leg_id="short-call",
                symbol="AAPL_210C",
                asset_class="OPTION",
                side="SELL_TO_OPEN",
                quantity=1,
                price=2.5,
                multiplier=100,
                strike=210.0,
                option_type="CALL",
                expiration="2026-08-21",
                metadata={"underlying_symbol": "AAPL"},
            ),
        ),
    )
    greek_legs = (
        OptionGreekProfile(
            leg_id="long-call",
            symbol="AAPL_200C",
            underlying_symbol="AAPL",
            quantity=1,
            multiplier=100,
            side="BUY_TO_OPEN",
            delta=0.55,
            gamma=0.025,
            vega=0.20,
            theta=-0.08,
            rho=0.10,
            implied_volatility=0.30,
            underlying_price=205.0,
            option_price=6.0,
            strike=200.0,
            expiration="2026-08-21",
            option_type="CALL",
        ),
        OptionGreekProfile(
            leg_id="short-call",
            symbol="AAPL_210C",
            underlying_symbol="AAPL",
            quantity=1,
            multiplier=100,
            side="SELL_TO_OPEN",
            delta=0.30,
            gamma=0.018,
            vega=0.15,
            theta=-0.05,
            rho=0.06,
            implied_volatility=0.28,
            underlying_price=205.0,
            option_price=2.5,
            strike=210.0,
            expiration="2026-08-21",
            option_type="CALL",
        ),
    )

    service = OptionsRiskService()
    approved = service.evaluate(
        spread_order,
        account,
        greek_legs,
        scenarios=(
            ScenarioShockProfile(
                scenario_id="down_10",
                underlying_shock_pct=-0.10,
            ),
            ScenarioShockProfile(
                scenario_id="up_10",
                underlying_shock_pct=0.10,
            ),
            ScenarioShockProfile(
                scenario_id="vol_up",
                volatility_shock=0.10,
            ),
        ),
    )
    assert approved.allowed
    assert approved.greeks is not None
    assert approved.greeks.delta == 25.0
    assert approved.greeks.gamma == 0.7
    assert approved.margin is not None
    assert approved.margin.defined_risk
    assert approved.margin.strategy_classification == "DEFINED_RISK_VERTICAL_SPREAD"
    assert approved.margin.width == 10.0
    assert approved.margin.margin_required == 1350.0
    assert approved.worst_scenario is not None

    naked_order = PreTradeRiskRequest(
        aggregate_id="agg-options-002",
        client_order_id="client-options-002",
        account_id="PAPER-001",
        order_type="LIMIT",
        time_in_force="DAY",
        strategy_name="NAKED_SHORT_CALL",
        legs=(
            PreTradeRiskLeg(
                leg_id="short-call",
                symbol="AAPL_220C",
                asset_class="OPTION",
                side="SELL_TO_OPEN",
                quantity=10,
                price=4.0,
                multiplier=100,
                strike=220.0,
                option_type="CALL",
                expiration="2026-08-21",
                metadata={"underlying_symbol": "AAPL"},
            ),
        ),
    )
    naked_greeks = (
        OptionGreekProfile(
            leg_id="short-call",
            symbol="AAPL_220C",
            underlying_symbol="AAPL",
            quantity=10,
            multiplier=100,
            side="SELL_TO_OPEN",
            delta=0.35,
            gamma=0.02,
            vega=0.18,
            theta=-0.06,
            rho=0.07,
            implied_volatility=0.32,
            underlying_price=205.0,
            option_price=4.0,
            strike=220.0,
            expiration="2026-08-21",
            option_type="CALL",
        ),
    )
    naked = service.evaluate(naked_order, account, naked_greeks)
    assert not naked.allowed
    assert "UNCOVERED_SHORT_OPTION" in naked.rejection_reasons
    assert "DEFINED_RISK" in naked.rejection_reasons
    assert naked.margin is not None
    assert naked.margin.uncovered_short_option
    assert naked.margin.maximum_loss is None

    strict_policy = OptionsRiskPolicy(
        maximum_absolute_delta=10.0,
        maximum_scenario_loss=100.0,
        maximum_scenario_loss_pct_of_net_liquidation=0.001,
    )
    strict = OptionsRiskService(strict_policy).evaluate(
        spread_order,
        account,
        greek_legs,
        scenarios=(
            ScenarioShockProfile(
                scenario_id="down_20",
                underlying_shock_pct=-0.20,
            ),
        ),
    )
    assert not strict.allowed
    assert "ABSOLUTE_DELTA" in strict.rejection_reasons
    assert (
        "MAXIMUM_SCENARIO_LOSS" in strict.rejection_reasons
        or "SCENARIO_LOSS_PCT_NET_LIQUIDATION"
        in strict.rejection_reasons
    )

    missing_greek = service.evaluate(
        spread_order,
        account,
        (greek_legs[0],),
    )
    assert not missing_greek.allowed
    assert "GREEK_LEG_COVERAGE" in missing_greek.rejection_reasons

    payload = dumps(approved)
    assert '"strategy_classification": "DEFINED_RISK_VERTICAL_SPREAD"' in payload
    assert '"recommendation": "APPROVE"' in payload
    print("All options Greeks, scenario stress, strategy margin, and defined-risk assertions passed.")

if __name__ == "__main__":
    main()
