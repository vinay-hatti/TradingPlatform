import pandas as pd

from trading_ai.strategy_engine.greeks_optimizer import GreeksOptimizer
from trading_ai.strategy_engine.strike_optimizer import StrikeOptimizer


def build_option_chain():
    rows = []
    underlying = 100.0

    for strike in [90, 95, 100, 105, 110]:
        call_delta = max(min(0.50 - ((strike - underlying) * 0.04), 0.95), 0.05)
        put_delta = -max(min(0.50 + ((strike - underlying) * 0.04), 0.95), 0.05)

        rows.append({
            "option_symbol": f"TESTC{strike}",
            "option_type": "CALL",
            "strike": strike,
            "expiry": "2026-02-20",
            "dte": 30,
            "bid": 2.95,
            "ask": 3.05,
            "mid": 3.00,
            "last": 3.00,
            "volume": 1000,
            "open_interest": 3000,
            "spread_pct": 0.05,
            "delta": call_delta,
            "gamma": 0.04,
            "theta": -0.05,
            "vega": 0.30,
            "rho": 0.05,
            "implied_volatility": 0.35,
        })

        rows.append({
            "option_symbol": f"TESTP{strike}",
            "option_type": "PUT",
            "strike": strike,
            "expiry": "2026-02-20",
            "dte": 30,
            "bid": 2.95,
            "ask": 3.05,
            "mid": 3.00,
            "last": 3.00,
            "volume": 1000,
            "open_interest": 3000,
            "spread_pct": 0.05,
            "delta": put_delta,
            "gamma": 0.04,
            "theta": -0.05,
            "vega": 0.30,
            "rho": -0.05,
            "implied_volatility": 0.35,
        })

    return pd.DataFrame(rows)


def print_profile(title, profile):
    warnings = ", ".join(profile.warnings) if profile.warnings else "-"

    print(f"\n--- {title} ---")
    print(f"Strategy       : {profile.strategy}")
    print(f"Net Delta      : {profile.net_delta}")
    print(f"Net Gamma      : {profile.net_gamma}")
    print(f"Net Theta      : {profile.net_theta}")
    print(f"Net Vega       : {profile.net_vega}")
    print(f"Exposure       : {profile.exposure_label}")
    print(f"Delta Score    : {profile.delta_score}")
    print(f"Gamma Score    : {profile.gamma_score}")
    print(f"Theta Score    : {profile.theta_score}")
    print(f"Vega Score     : {profile.vega_score}")
    print(f"Composite      : {profile.composite_score}")
    print(f"Allowed        : {profile.allowed}")
    print(f"Warnings       : {warnings}")
    print(f"Reason         : {profile.reason}")


def main():
    optimizer = GreeksOptimizer()
    chain = build_option_chain()

    strike_optimizer = StrikeOptimizer(
        min_volume=100,
        min_open_interest=500,
        max_spread_pct=0.20,
    )

    print("\n========== Greeks Optimizer Test ==========")

    long_call = optimizer.analyze_single_leg(
        symbol="TEST",
        strategy="LONG_CALL",
        delta=0.52,
        gamma=0.04,
        theta=-0.05,
        vega=0.30,
        rho=0.05,
    )
    print_profile("LONG_CALL", long_call)

    long_put = optimizer.analyze_single_leg(
        symbol="TEST",
        strategy="LONG_PUT",
        delta=-0.52,
        gamma=0.04,
        theta=-0.05,
        vega=0.30,
        rho=-0.05,
    )
    print_profile("LONG_PUT", long_put)

    iron_condor = optimizer.analyze_multi_leg(
        symbol="TEST",
        strategy="IRON_CONDOR",
        legs=[
            {"action": "SELL", "quantity": 1, "delta": -0.20, "gamma": 0.03, "theta": -0.04, "vega": 0.25},
            {"action": "BUY", "quantity": 1, "delta": -0.10, "gamma": 0.02, "theta": -0.02, "vega": 0.15},
            {"action": "SELL", "quantity": 1, "delta": 0.20, "gamma": 0.03, "theta": -0.04, "vega": 0.25},
            {"action": "BUY", "quantity": 1, "delta": 0.10, "gamma": 0.02, "theta": -0.02, "vega": 0.15},
        ],
    )
    print_profile("IRON_CONDOR", iron_condor)

    strike_candidates = strike_optimizer.optimize(
        symbol="TEST",
        strategy="LONG_CALL",
        underlying_price=100.0,
        option_chain=chain,
        top_n=5,
    )

    optimized = optimizer.optimize_candidates(
        strike_candidates,
        symbol="TEST",
    )

    print("\n--- Optimized Strike Candidates ---")
    for idx, c in enumerate(optimized, start=1):
        profile = getattr(c, "greeks_profile")
        print(
            f"{idx}. Strike={c.strike:>6.2f} "
            f"OriginalScore={c.composite_score:>6.2f} "
            f"GreeksScore={profile.composite_score:>6.2f} "
            f"Exposure={profile.exposure_label} "
            f"Allowed={profile.allowed}"
        )

    print("==========================================")


if __name__ == "__main__":
    main()
