from trading_ai.strategy_engine.multi_strategy_builder import (
    MultiStrategyBuilder,
)
from trading_ai.strategy_engine.probability_engine import (
    ProbabilityEngine,
)
from trading_ai.strategy_engine.probability_policy import (
    ProbabilityPolicy,
)


def print_profile(profile):
    print(
        f"\n========== {profile.strategy} =========="
    )

    print(
        f"Underlying                  : "
        f"${profile.underlying_price:.2f}"
    )

    print(
        f"Horizon                     : "
        f"{profile.horizon_days} days"
    )

    print(
        f"Volatility                  : "
        f"{profile.volatility:.2%}"
    )

    print(
        f"Simulations                 : "
        f"{profile.simulation_count:,}"
    )

    print(
        f"Probability of Profit       : "
        f"{profile.probability_of_profit:.2%}"
    )

    print(
        f"Probability of Loss         : "
        f"{profile.probability_of_loss:.2%}"
    )

    print(
        f"Probability of Breakeven    : "
        f"{profile.probability_of_breakeven:.2%}"
    )

    print(
        f"Probability of Max Profit   : "
        f"{profile.probability_of_max_profit}"
    )

    print(
        f"Probability of Max Loss     : "
        f"{profile.probability_of_max_loss}"
    )

    print(
        f"Probability Profit Target   : "
        f"{profile.probability_profit_target}"
    )

    print(
        f"Probability Stop Loss       : "
        f"{profile.probability_stop_loss}"
    )

    print(
        f"Expected Value              : "
        f"${profile.expected_value:.2f}"
    )

    print(
        f"Expected Return on Capital  : "
        f"{profile.expected_return_on_capital:.2%}"
    )

    print(
        f"Expected Return on Risk     : "
        f"{profile.expected_return_on_risk:.2%}"
    )

    print(
        f"Average Profit              : "
        f"${profile.average_profit:.2f}"
    )

    print(
        f"Average Loss                : "
        f"${profile.average_loss:.2f}"
    )

    print(
        f"Median PnL                  : "
        f"${profile.median_pnl:.2f}"
    )

    print(
        f"PnL Std Dev                 : "
        f"${profile.pnl_standard_deviation:.2f}"
    )

    print(
        f"VaR 95                      : "
        f"${profile.value_at_risk_95:.2f}"
    )

    print(
        f"CVaR 95                     : "
        f"${profile.conditional_value_at_risk_95:.2f}"
    )

    print(
        f"Expected Terminal Price     : "
        f"${profile.expected_terminal_price:.2f}"
    )

    print(
        f"Terminal 5%-95% Range       : "
        f"${profile.lower_terminal_price_5pct:.2f} - "
        f"${profile.upper_terminal_price_95pct:.2f}"
    )

    print(
        f"Confidence                  : "
        f"{profile.confidence_score:.2f} "
        f"({profile.confidence_grade})"
    )

    print(
        f"Method                      : "
        f"{profile.method}"
    )

    warnings = (
        ", ".join(profile.warnings)
        if profile.warnings
        else "-"
    )

    print(
        f"Warnings                    : "
        f"{warnings}"
    )


def main():
    builder = MultiStrategyBuilder()

    policy = ProbabilityPolicy(
        simulation_count=50000,
        random_seed=42,
        risk_free_rate=0.04,
        dividend_yield=0.0,
    )

    engine = ProbabilityEngine(
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

    profiles = []

    for structure in [
        bull_call,
        bull_put,
        iron_condor,
        long_straddle,
    ]:
        profile = engine.analyze(
            structure=structure,
            volatility=0.30,
            horizon_days=30,
            include_touch_probabilities=True,
        )

        profiles.append(profile)
        print_profile(profile)

    # -------------------------------------------------
    # Focused assertions
    # -------------------------------------------------

    for profile in profiles:
        assert profile.valid is True

        assert (
            0.0
            <= profile.probability_of_profit
            <= 1.0
        )

        assert (
            0.0
            <= profile.probability_of_loss
            <= 1.0
        )

        total_probability = (
            profile.probability_of_profit
            + profile.probability_of_loss
            + profile.probability_of_breakeven
        )

        assert abs(
            total_probability - 1.0
        ) < 0.001

        assert profile.simulation_count == 50000
        assert profile.expected_terminal_price > 0
        assert profile.confidence_score > 0

    bull_put_profile = next(
        profile
        for profile in profiles
        if profile.strategy
        == "BULL_PUT_SPREAD"
    )

    assert (
        bull_put_profile.probability_of_profit
        > 0.0
    )

    assert (
        bull_put_profile.probability_of_max_loss
        is not None
    )

    condor_profile = next(
        profile
        for profile in profiles
        if profile.strategy
        == "IRON_CONDOR"
    )

    assert (
        condor_profile
        .probability_inside_breakevens
        is not None
    )

    straddle_profile = next(
        profile
        for profile in profiles
        if profile.strategy
        == "LONG_STRADDLE"
    )

    assert (
        straddle_profile.probability_touch_upper
        is not None
    )

    assert (
        straddle_profile.probability_touch_lower
        is not None
    )

    # Deterministic seed test.
    repeated = engine.analyze(
        structure=bull_put,
        volatility=0.30,
        horizon_days=30,
        include_touch_probabilities=False,
    )

    assert (
        repeated.probability_of_profit
        == bull_put_profile.probability_of_profit
    )

    print(
        "\nAll probability-engine assertions passed."
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
