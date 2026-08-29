from trading_ai.strategy_engine.multi_strategy_builder import (
    MultiStrategyBuilder,
)
from trading_ai.strategy_engine.scenario_definition import (
    ScenarioDefinition,
)
from trading_ai.strategy_engine.scenario_engine import (
    ScenarioEngine,
)
from trading_ai.strategy_engine.scenario_policy import (
    ScenarioPolicy,
)
from trading_ai.strategy_engine.scenario_service import (
    ScenarioService,
)


def print_result(result):
    print(
        f"\n========== "
        f"{result.symbol} "
        f"{result.strategy} =========="
    )

    print(
        f"Base Price               : "
        f"${result.underlying_price:.2f}"
    )

    print(
        f"Base Volatility          : "
        f"{result.base_volatility:.2%}"
    )

    print(
        f"Days to Expiry           : "
        f"{result.days_to_expiry}"
    )

    print(
        f"Capital Required         : "
        f"${result.capital_required:.2f}"
    )

    print(
        f"Maximum Loss             : "
        f"${result.maximum_loss:.2f}"
    )

    print(
        f"Base PnL                 : "
        f"${result.base_pnl:.2f}"
    )

    print(
        f"Worst Scenario           : "
        f"{result.worst_scenario_name}"
    )

    print(
        f"Worst Scenario PnL       : "
        f"${result.worst_scenario_pnl:.2f}"
    )

    print(
        f"Maximum Stress Loss      : "
        f"${result.maximum_stress_loss:.2f}"
    )

    print(
        f"Stress Loss / Capital    : "
        f"{result.maximum_stress_loss_pct_of_capital:.2%}"
    )

    print(
        f"Stress Score             : "
        f"{result.stress_score:.2f}"
    )

    print(
        f"Stress Grade             : "
        f"{result.stress_grade}"
    )

    print(
        f"Risk Severity            : "
        f"{result.risk_severity}"
    )

    print(
        f"Allowed                  : "
        f"{result.allowed}"
    )

    for point in result.scenario_points:
        print(
            f"  {point.scenario_name:<24} "
            f"Price=${point.stressed_underlying_price:>8.2f} "
            f"IV={point.stressed_volatility:>7.2%} "
            f"DTE={point.stressed_days_to_expiry:>3} "
            f"PnL=${point.stressed_pnl:>9.2f} "
            f"Passed={point.passed}"
        )


def main():
    builder = MultiStrategyBuilder()

    policy = ScenarioPolicy(
        maximum_stress_loss_pct_of_capital=1.25,
        maximum_stress_loss_pct_of_max_loss=1.05,
    )

    engine = ScenarioEngine(
        policy=policy
    )

    bull_call = builder.bull_call_spread(
        symbol="TEST",
        underlying_price=100.0,
        expiry="2026-08-21",
        long_strike=100.0,
        short_strike=110.0,
        long_premium=6.0,
        short_premium=2.0,
    )

    bull_put = builder.bull_put_spread(
        symbol="TEST",
        underlying_price=100.0,
        expiry="2026-08-21",
        short_strike=95.0,
        long_strike=90.0,
        short_premium=3.0,
        long_premium=1.0,
    )

    iron_condor = builder.iron_condor(
        symbol="TEST",
        underlying_price=100.0,
        expiry="2026-08-21",
        long_put_strike=85.0,
        short_put_strike=90.0,
        short_call_strike=110.0,
        long_call_strike=115.0,
        long_put_premium=0.50,
        short_put_premium=1.50,
        short_call_premium=1.60,
        long_call_premium=0.60,
    )

    long_straddle = builder.long_straddle(
        symbol="TEST",
        underlying_price=100.0,
        expiry="2026-08-21",
        strike=100.0,
        call_premium=5.0,
        put_premium=4.8,
    )

    results = []

    configurations = [
        (
            bull_call,
            400.0,
            400.0,
        ),
        (
            bull_put,
            300.0,
            300.0,
        ),
        (
            iron_condor,
            300.0,
            300.0,
        ),
        (
            long_straddle,
            980.0,
            980.0,
        ),
    ]

    for (
        structure,
        capital_required,
        maximum_loss,
    ) in configurations:
        result = engine.analyze(
            structure=structure,
            volatility=0.30,
            days_to_expiry=30,
            capital_required=(
                capital_required
            ),
            maximum_loss=maximum_loss,
        )

        results.append(result)
        print_result(result)

    # ---------------------------------------------
    # Custom scenario test
    # ---------------------------------------------

    custom_scenarios = [
        ScenarioDefinition(
            name="CUSTOM_CRASH",
            description=(
                "Underlying falls 25% and IV doubles"
            ),
            underlying_shock_pct=-0.25,
            volatility_shock_pct=1.00,
            days_forward=2,
            category="CUSTOM",
            severity="CRITICAL",
        ),
        ScenarioDefinition(
            name="CUSTOM_RALLY",
            description=(
                "Underlying rises 20% and IV falls 40%"
            ),
            underlying_shock_pct=0.20,
            volatility_shock_pct=-0.40,
            days_forward=2,
            category="CUSTOM",
            severity="SEVERE",
        ),
    ]

    custom_result = engine.analyze(
        structure=bull_put,
        volatility=0.30,
        days_to_expiry=30,
        capital_required=300.0,
        maximum_loss=300.0,
        scenarios=custom_scenarios,
    )

    print_result(custom_result)

    # ---------------------------------------------
    # Service test
    # ---------------------------------------------

    service = ScenarioService(
        policy=policy
    )

    service_result = (
        service.analyze_strategy(
            structure=bull_call,
            volatility=0.30,
            days_to_expiry=30,
            capital_required=400.0,
            maximum_loss=400.0,
        )
    )

    # ---------------------------------------------
    # Focused assertions
    # ---------------------------------------------

    for result in results:
        assert result.valid is True
        assert result.scenario_points
        assert result.worst_scenario_name
        assert result.best_scenario_name

        assert (
            result.maximum_stress_loss
            >= 0.0
        )

        assert (
            0.0
            <= result.stress_score
            <= 100.0
        )

    bull_call_result = next(
        result
        for result in results
        if result.strategy
        == "BULL_CALL_SPREAD"
    )

    crash_point = next(
        point
        for point
        in bull_call_result.scenario_points
        if point.scenario_name
        == "CRASH_VOL_SPIKE"
    )

    rally_point = next(
        point
        for point
        in bull_call_result.scenario_points
        if point.scenario_name
        == "PRICE_UP_20"
    )

    assert (
        crash_point.stressed_pnl
        < rally_point.stressed_pnl
    )

    bull_put_result = next(
        result
        for result in results
        if result.strategy
        == "BULL_PUT_SPREAD"
    )

    down_20 = next(
        point
        for point
        in bull_put_result.scenario_points
        if point.scenario_name
        == "PRICE_DOWN_20"
    )

    assert down_20.stressed_pnl < 0

    condor_result = next(
        result
        for result in results
        if result.strategy
        == "IRON_CONDOR"
    )

    assert (
        condor_result.downside_scenario_count
        > 0
    )

    assert custom_result.valid is True
    assert len(
        custom_result.scenario_points
    ) == 2

    assert service_result.valid is True

    print(
        "\nAll scenario-engine assertions passed."
    )

    print(
        "============================================="
    )


if __name__ == "__main__":
    main()
