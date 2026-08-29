import pandas as pd

from trading_ai.strategy_engine.liquidity_engine import LiquidityEngine
from trading_ai.strategy_engine.liquidity_thresholds import LiquidityThresholds


def build_option_chain():
    return pd.DataFrame([
        {
            "option_symbol": "AAPL260220C00300000",
            "option_type": "CALL",
            "strike": 300.0,
            "expiry": "2026-02-20",
            "dte": 30,
            "bid": 5.00,
            "ask": 5.10,
            "mid": 5.05,
            "last": 5.04,
            "volume": 5000,
            "open_interest": 12000,
            "bid_size": 75,
            "ask_size": 80,
        },
        {
            "option_symbol": "AAPL260220C00305000",
            "option_type": "CALL",
            "strike": 305.0,
            "expiry": "2026-02-20",
            "dte": 30,
            "bid": 3.80,
            "ask": 4.20,
            "mid": 4.00,
            "last": 3.95,
            "volume": 650,
            "open_interest": 1800,
            "bid_size": 12,
            "ask_size": 15,
        },
        {
            "option_symbol": "AAPL260220C00310000",
            "option_type": "CALL",
            "strike": 310.0,
            "expiry": "2026-02-20",
            "dte": 30,
            "bid": 1.00,
            "ask": 2.00,
            "mid": 1.50,
            "last": 1.40,
            "volume": 30,
            "open_interest": 75,
            "bid_size": 1,
            "ask_size": 2,
        },
        {
            "option_symbol": "AAPL260220C00315000",
            "option_type": "CALL",
            "strike": 315.0,
            "expiry": "2026-02-20",
            "dte": 30,
            "bid": 0.00,
            "ask": 0.50,
            "mid": 0.25,
            "last": 0.30,
            "volume": 5,
            "open_interest": 20,
            "bid_size": 0,
            "ask_size": 1,
        },
    ])


def print_profile(profile):
    warnings = ", ".join(profile.warnings) if profile.warnings else "-"

    print(
        f"{profile.option_symbol:<24} "
        f"Liq={profile.liquidity_score:>6.2f} "
        f"Exec={profile.execution_score:>6.2f} "
        f"Grade={profile.liquidity_grade:<3} "
        f"Quality={profile.execution_quality:<12} "
        f"Spread={profile.spread_pct:>7.2%} "
        f"Capacity={profile.estimated_capacity:>4} "
        f"Buy={profile.estimated_buy_price:>7.4f} "
        f"Sell={profile.estimated_sell_price:>7.4f} "
        f"Slippage=${profile.estimated_round_trip_slippage:>7.2f} "
        f"Allowed={profile.allowed} "
        f"Warnings={warnings}"
    )


def main():
    chain = build_option_chain()

    thresholds = LiquidityThresholds(
        min_volume=50,
        min_open_interest=100,
        max_spread_pct=0.30,
        preferred_spread_pct=0.10,
        minimum_liquidity_score=55.0,
        minimum_execution_score=50.0,
    )

    engine = LiquidityEngine(thresholds=thresholds)

    print("\n========== Institutional Liquidity Engine ==========")

    print("\n--- Contract Ranking: 1 Contract ---")
    profiles = engine.rank_contracts(
        symbol="AAPL",
        option_chain=chain,
        requested_contracts=1,
    )

    for profile in profiles:
        print_profile(profile)

    print("\n--- Contract Ranking: 20 Contracts ---")
    profiles = engine.rank_contracts(
        symbol="AAPL",
        option_chain=chain,
        requested_contracts=20,
    )

    for profile in profiles:
        print_profile(profile)

    print("\n--- Bull Call Spread Package ---")

    long_leg = chain.iloc[0].to_dict()
    short_leg = chain.iloc[1].to_dict()

    spread = engine.analyze_multi_leg(
        symbol="AAPL",
        strategy="BULL_CALL_SPREAD",
        requested_contracts=3,
        legs=[
            {
                "action": "BUY",
                "quantity": 1,
                "contract": long_leg,
            },
            {
                "action": "SELL",
                "quantity": 1,
                "contract": short_leg,
            },
        ],
    )

    spread_warnings = (
        ", ".join(spread.warnings)
        if spread.warnings
        else "-"
    )

    print(f"Strategy              : {spread.strategy}")
    print(f"Leg Count             : {spread.leg_count}")
    print(f"Package Mid           : {spread.package_mid:.4f}")
    print(f"Estimated Package     : {spread.estimated_package_price:.4f}")
    print(f"Package Spread        : {spread.package_spread_pct:.2%}")
    print(f"Minimum Leg Score     : {spread.minimum_leg_liquidity_score:.2f}")
    print(f"Average Leg Score     : {spread.average_leg_liquidity_score:.2f}")
    print(f"Package Score         : {spread.package_liquidity_score:.2f}")
    print(f"Execution Score       : {spread.execution_score:.2f}")
    print(f"Round Trip Slippage   : ${spread.estimated_round_trip_slippage:.2f}")
    print(f"Slippage %            : {spread.estimated_round_trip_slippage_pct:.2f}%")
    print(f"Weakest Leg           : {spread.weakest_leg}")
    print(f"Grade                 : {spread.liquidity_grade}")
    print(f"Execution Quality     : {spread.execution_quality}")
    print(f"Allowed               : {spread.allowed}")
    print(f"Warnings              : {spread_warnings}")

    one_contract_profiles = engine.rank_contracts(
        symbol="AAPL",
        option_chain=chain,
        requested_contracts=1,
    )

    best = one_contract_profiles[0]
    worst = one_contract_profiles[-1]

    assert best.option_symbol == "AAPL260220C00300000"
    assert best.allowed is True
    assert best.liquidity_score > worst.liquidity_score

    zero_bid = next(
        profile
        for profile in one_contract_profiles
        if profile.option_symbol == "AAPL260220C00315000"
    )

    assert zero_bid.allowed is False
    assert "Zero bid" in zero_bid.warnings

    print("\nAll liquidity assertions passed.")
    print("====================================================")


if __name__ == "__main__":
    main()
