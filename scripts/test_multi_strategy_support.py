from trading_ai.strategy_engine.multi_strategy_builder import (
    MultiStrategyBuilder,
)
from trading_ai.strategy_engine.multi_strategy_service import (
    MultiStrategyService,
)
from trading_ai.strategy_engine.multi_strategy_validator import (
    MultiStrategyValidator,
)
from trading_ai.strategy_engine.strategy_payoff_engine import (
    StrategyPayoffEngine,
)


def print_profile(
    structure,
    profile,
):
    print(
        f"\n========== "
        f"{structure.strategy} =========="
    )

    print(
        f"Symbol              : "
        f"{structure.symbol}"
    )

    print(
        f"Legs                : "
        f"{len(structure.legs)}"
    )

    print(
        f"Expiries            : "
        f"{structure.expiries}"
    )

    print(
        f"Net Debit           : "
        f"${profile.net_debit:.2f}"
    )

    print(
        f"Net Credit          : "
        f"${profile.net_credit:.2f}"
    )

    print(
        f"Maximum Profit      : "
        f"{profile.maximum_profit}"
    )

    print(
        f"Maximum Loss        : "
        f"{profile.maximum_loss}"
    )

    print(
        f"Break Evens         : "
        f"{profile.break_even_points}"
    )

    print(
        f"Risk/Reward         : "
        f"{profile.risk_reward_ratio}"
    )

    print(
        f"Return on Risk      : "
        f"{profile.return_on_risk_pct}"
    )

    print(
        f"Current PnL         : "
        f"${profile.profit_at_current_price:.2f}"
    )

    print(
        f"Capital Required    : "
        f"${profile.capital_required:.2f}"
    )

    print(
        f"Expected Profit     : "
        f"${profile.expected_profit:.2f}"
    )

    print(
        f"Expected Return     : "
        f"{profile.expected_return_pct:.2%}"
    )

    print(
        f"Net Delta           : "
        f"{profile.net_delta:.4f}"
    )

    print(
        f"Net Theta           : "
        f"{profile.net_theta:.4f}"
    )

    print(
        f"Net Vega            : "
        f"{profile.net_vega:.4f}"
    )

    print(
        f"Valuation Mode      : "
        f"{profile.valuation_mode}"
    )

    print(
        f"Defined Risk        : "
        f"{profile.defined_risk}"
    )

    print(
        f"Unlimited Profit    : "
        f"{profile.unlimited_profit}"
    )

    print(
        f"Valid               : "
        f"{profile.valid}"
    )

    warnings = (
        ", ".join(profile.warnings)
        if profile.warnings
        else "-"
    )

    notes = (
        ", ".join(profile.notes)
        if profile.notes
        else "-"
    )

    print(
        f"Warnings            : "
        f"{warnings}"
    )

    print(
        f"Notes               : "
        f"{notes}"
    )


def main():
    builder = MultiStrategyBuilder()
    validator = MultiStrategyValidator()
    payoff_engine = StrategyPayoffEngine()
    service = MultiStrategyService()

    print(
        "\n========== Multi-Strategy Support =========="
    )

    bull_call = builder.bull_call_spread(
        symbol="AAPL",
        underlying_price=100.0,
        expiry="2026-08-21",
        long_strike=100.0,
        short_strike=110.0,
        long_premium=6.00,
        short_premium=2.00,
    )

    bear_put = builder.bear_put_spread(
        symbol="AAPL",
        underlying_price=100.0,
        expiry="2026-08-21",
        long_strike=100.0,
        short_strike=90.0,
        long_premium=5.50,
        short_premium=1.50,
    )

    bull_put = builder.bull_put_spread(
        symbol="AAPL",
        underlying_price=100.0,
        expiry="2026-08-21",
        short_strike=95.0,
        long_strike=90.0,
        short_premium=3.00,
        long_premium=1.00,
    )

    bear_call = builder.bear_call_spread(
        symbol="AAPL",
        underlying_price=100.0,
        expiry="2026-08-21",
        short_strike=105.0,
        long_strike=110.0,
        short_premium=3.20,
        long_premium=1.20,
    )

    iron_condor = builder.iron_condor(
        symbol="AAPL",
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
        symbol="AAPL",
        underlying_price=100.0,
        expiry="2026-08-21",
        strike=100.0,
        call_premium=5.00,
        put_premium=4.80,
    )

    long_strangle = builder.long_strangle(
        symbol="AAPL",
        underlying_price=100.0,
        expiry="2026-08-21",
        put_strike=95.0,
        call_strike=105.0,
        put_premium=3.00,
        call_premium=3.20,
    )

    calendar_call = builder.calendar(
        symbol="AAPL",
        option_type="CALL",
        underlying_price=100.0,
        strike=100.0,
        short_expiry="2026-08-21",
        long_expiry="2026-09-18",
        short_premium=3.00,
        long_premium=5.50,
    )

    diagonal_call = builder.diagonal(
        symbol="AAPL",
        option_type="CALL",
        underlying_price=100.0,
        short_strike=105.0,
        long_strike=100.0,
        short_expiry="2026-08-21",
        long_expiry="2026-09-18",
        short_premium=2.50,
        long_premium=5.50,
    )

    same_expiry_structures = [
        bull_call,
        bear_put,
        bull_put,
        bear_call,
        iron_condor,
        long_straddle,
        long_strangle,
    ]

    profiles = {}

    for structure in same_expiry_structures:
        validation = validator.validate(
            structure
        )

        assert validation.valid is True

        profile = payoff_engine.analyze(
            structure
        )

        profiles[structure.strategy] = profile

        print_profile(
            structure,
            profile,
        )

    calendar_profile_unvalued = (
        payoff_engine.analyze(
            calendar_call
        )
    )

    print_profile(
        calendar_call,
        calendar_profile_unvalued,
    )

    calendar_keys = {
        (
            leg.option_symbol
            or (
                f"{leg.option_type}_"
                f"{leg.strike}_"
                f"{leg.expiry}_"
                f"{leg.normalized_action}"
            )
        ): (
            1.20
            if leg.normalized_action
            == "SELL"
            else 4.80
        )
        for leg in calendar_call.legs
    }

    calendar_profile_valued = (
        payoff_engine.analyze(
            calendar_call,
            estimated_leg_values=calendar_keys,
        )
    )

    print_profile(
        calendar_call,
        calendar_profile_valued,
    )

    diagonal_keys = {
        (
            leg.option_symbol
            or (
                f"{leg.option_type}_"
                f"{leg.strike}_"
                f"{leg.expiry}_"
                f"{leg.normalized_action}"
            )
        ): (
            0.80
            if leg.normalized_action
            == "SELL"
            else 6.20
        )
        for leg in diagonal_call.legs
    }

    diagonal_profile = payoff_engine.analyze(
        diagonal_call,
        estimated_leg_values=diagonal_keys,
    )

    print_profile(
        diagonal_call,
        diagonal_profile,
    )

    # ---------------------------------------------
    # Focused payoff assertions
    # ---------------------------------------------

    bull_call_profile = profiles[
        "BULL_CALL_SPREAD"
    ]

    assert bull_call_profile.net_debit == 400.0
    assert bull_call_profile.maximum_profit == 600.0
    assert bull_call_profile.maximum_loss == 400.0
    assert len(
        bull_call_profile.break_even_points
    ) == 1

    bull_put_profile = profiles[
        "BULL_PUT_SPREAD"
    ]

    assert bull_put_profile.net_credit == 200.0
    assert bull_put_profile.maximum_profit == 200.0
    assert bull_put_profile.maximum_loss == 300.0

    iron_condor_profile = profiles[
        "IRON_CONDOR"
    ]

    assert iron_condor_profile.net_credit == 200.0
    assert iron_condor_profile.maximum_profit == 200.0
    assert iron_condor_profile.maximum_loss == 300.0
    assert len(
        iron_condor_profile.break_even_points
    ) == 2

    straddle_profile = profiles[
        "LONG_STRADDLE"
    ]

    assert straddle_profile.unlimited_profit is True
    assert straddle_profile.maximum_loss == 980.0
    assert len(
        straddle_profile.break_even_points
    ) == 2

    assert (
        calendar_profile_unvalued.valuation_mode
        == "MULTI_EXPIRATION_UNVALUED"
    )

    assert (
        calendar_profile_valued.valuation_mode
        == "MARK_TO_MODEL"
    )

    assert calendar_profile_valued.valid is True

    assert (
        diagonal_profile.valuation_mode
        == "MARK_TO_MODEL"
    )

    # ---------------------------------------------
    # Service test
    # ---------------------------------------------

    structure, profile = (
        service.build_and_analyze(
            symbol="MSFT",
            strategy="BULL_CALL_SPREAD",
            underlying_price=450.0,
            legs=[
                {
                    "option_type": "CALL",
                    "action": "BUY",
                    "strike": 450.0,
                    "expiry": "2026-08-21",
                    "premium": 12.0,
                },
                {
                    "option_type": "CALL",
                    "action": "SELL",
                    "strike": 460.0,
                    "expiry": "2026-08-21",
                    "premium": 7.0,
                },
            ],
        )
    )

    assert structure.strategy == "BULL_CALL_SPREAD"
    assert profile.valid is True
    assert profile.maximum_loss == 500.0
    assert profile.maximum_profit == 500.0

    print(
        "\nAll multi-strategy assertions passed."
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
