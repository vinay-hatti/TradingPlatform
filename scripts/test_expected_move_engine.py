import pandas as pd

from trading_ai.strategy_engine.expected_move_engine import (
    ExpectedMoveEngine,
)
from trading_ai.strategy_engine.expected_move_strategy_fit import (
    ExpectedMoveStrategyFit,
)


def build_option_chain():
    rows = []

    underlying_price = 100.0

    expiries = [
        ("2026-02-06", 7),
        ("2026-02-20", 21),
        ("2026-03-20", 49),
    ]

    strikes = [
        90.0,
        95.0,
        100.0,
        105.0,
        110.0,
    ]

    for expiry, dte in expiries:
        for strike in strikes:
            distance = abs(
                strike - underlying_price
            )

            time_value = (
                1.50
                + dte * 0.035
                + distance * 0.025
            )

            call_intrinsic = max(
                underlying_price - strike,
                0.0,
            )

            put_intrinsic = max(
                strike - underlying_price,
                0.0,
            )

            call_mid = (
                call_intrinsic + time_value
            )

            put_mid = (
                put_intrinsic + time_value
            )

            rows.append({
                "option_symbol": (
                    f"TEST{expiry.replace('-', '')}"
                    f"C{int(strike)}"
                ),
                "option_type": "CALL",
                "strike": strike,
                "expiry": expiry,
                "dte": dte,
                "bid": round(
                    call_mid - 0.05,
                    2,
                ),
                "ask": round(
                    call_mid + 0.05,
                    2,
                ),
                "mid": round(call_mid, 2),
                "last": round(call_mid, 2),
                "implied_volatility": (
                    0.32 + dte * 0.0005
                ),
            })

            rows.append({
                "option_symbol": (
                    f"TEST{expiry.replace('-', '')}"
                    f"P{int(strike)}"
                ),
                "option_type": "PUT",
                "strike": strike,
                "expiry": expiry,
                "dte": dte,
                "bid": round(
                    put_mid - 0.05,
                    2,
                ),
                "ask": round(
                    put_mid + 0.05,
                    2,
                ),
                "mid": round(put_mid, 2),
                "last": round(put_mid, 2),
                "implied_volatility": (
                    0.33 + dte * 0.0005
                ),
            })

    return pd.DataFrame(rows)


def print_profile(profile):
    print(
        f"\n========== Expected Move: "
        f"{profile.horizon_days} Days =========="
    )

    print(
        f"Symbol                    : "
        f"{profile.symbol}"
    )

    print(
        f"Underlying                : "
        f"${profile.underlying_price:.2f}"
    )

    print(
        f"IV Move                   : "
        f"${profile.iv_move:.2f}"
    )

    print(
        f"Straddle Move             : "
        f"${profile.straddle_move:.2f}"
    )

    print(
        f"Historical Move           : "
        f"${profile.historical_move:.2f}"
    )

    print(
        f"ATR Move                  : "
        f"${profile.atr_move:.2f}"
    )

    print(
        f"Blended Move              : "
        f"${profile.blended_move:.2f}"
    )

    print(
        f"Blended Move %            : "
        f"{profile.blended_move_pct:.2f}%"
    )

    print(
        f"Expected Range            : "
        f"${profile.lower_bound:.2f} - "
        f"${profile.upper_bound:.2f}"
    )

    print(
        f"2-Sigma Range             : "
        f"${profile.lower_bound_2sigma:.2f} - "
        f"${profile.upper_bound_2sigma:.2f}"
    )

    print(
        f"Daily Move                : "
        f"${profile.daily_move:.2f}"
    )

    print(
        f"Weekly Move               : "
        f"${profile.weekly_move:.2f}"
    )

    print(
        f"Monthly Move              : "
        f"${profile.monthly_move:.2f}"
    )

    print(
        f"Source Count              : "
        f"{profile.source_count}"
    )

    print(
        f"Source Agreement          : "
        f"{profile.source_agreement_score:.2f}"
    )

    print(
        f"Confidence                : "
        f"{profile.confidence_score:.2f} "
        f"({profile.confidence_grade})"
    )

    print(
        f"Move Regime               : "
        f"{profile.move_regime}"
    )

    print(
        f"Expansion Signal          : "
        f"{profile.expansion_signal}"
    )

    print(
        f"Dominant Source           : "
        f"{profile.dominant_source}"
    )

    warnings = (
        ", ".join(profile.warnings)
        if profile.warnings
        else "-"
    )

    print(
        f"Warnings                  : "
        f"{warnings}"
    )

    print("\nSources:")

    for source in profile.sources:
        print(
            f"  {source.source:<24} "
            f"Available={str(source.available):<5} "
            f"Move=${source.move_dollars:>7.2f} "
            f"Move%={source.move_pct:>6.2f}% "
            f"Weight={source.weight:.2f}"
        )


def main():
    option_chain = build_option_chain()

    engine = ExpectedMoveEngine(
        straddle_multiplier=0.85,
    )

    print(
        "\n========== Institutional Expected "
        "Move Engine =========="
    )

    direct_profile = engine.analyze(
        symbol="TEST",
        underlying_price=100.0,
        horizon_days=21,
        implied_volatility=0.35,
        historical_volatility=0.24,
        atr=1.50,
        atm_call_price=3.20,
        atm_put_price=3.10,
    )

    print_profile(direct_profile)

    chain_profile = engine.analyze_from_option_chain(
        symbol="TEST",
        underlying_price=100.0,
        horizon_days=21,
        option_chain=option_chain,
        implied_volatility=0.35,
        historical_volatility=0.24,
        atr=1.50,
        target_expiry="2026-02-20",
    )

    print_profile(chain_profile)

    print("\n========== Multiple Horizons ==========")

    profiles = engine.horizon_profiles(
        symbol="TEST",
        underlying_price=100.0,
        horizons=[1, 3, 5, 10, 21, 30],
        implied_volatility=0.35,
        historical_volatility=0.24,
        atr=1.50,
        atm_call_price=3.20,
        atm_put_price=3.10,
    )

    for profile in profiles:
        print(
            f"{profile.horizon_days:>3}D | "
            f"Move=${profile.blended_move:>6.2f} | "
            f"Move%={profile.blended_move_pct:>6.2f}% | "
            f"Range="
            f"${profile.lower_bound:.2f}-"
            f"${profile.upper_bound:.2f} | "
            f"Confidence="
            f"{profile.confidence_score:.2f}"
        )

    strategy_fit = ExpectedMoveStrategyFit()

    print("\n========== Strategy Fit ==========")

    strategies = [
        "LONG_CALL",
        "LONG_PUT",
        "BULL_CALL_SPREAD",
        "BULL_PUT_SPREAD",
        "IRON_CONDOR",
        "LONG_STRADDLE",
    ]

    for strategy in strategies:
        score = strategy_fit.score(
            strategy=strategy,
            expected_move_profile=chain_profile,
        )

        print(
            f"{strategy:<22} "
            f"ExpectedMoveFit={score:>6.2f}"
        )

    print(
        "Recommendation           : "
        f"{strategy_fit.recommendation(chain_profile)}"
    )

    # -------------------------------------------------
    # Focused assertions
    # -------------------------------------------------

    assert direct_profile.blended_move > 0
    assert direct_profile.lower_bound < 100.0
    assert direct_profile.upper_bound > 100.0
    assert direct_profile.source_count == 4

    assert chain_profile.straddle_move > 0
    assert chain_profile.confidence_score > 0
    assert chain_profile.confidence_grade in {
        "A+",
        "A",
        "A-",
        "B+",
        "B",
        "C",
        "D",
        "F",
    }

    assert len(profiles) == 6
    assert profiles[-1].blended_move >= profiles[0].blended_move

    print("\nAll expected-move assertions passed.")
    print("================================================")


if __name__ == "__main__":
    main()
