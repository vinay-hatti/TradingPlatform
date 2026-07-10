import pandas as pd

from trading_ai.strategy_engine.expiration_optimizer import ExpirationOptimizer
from trading_ai.strategy_engine.volatility_engine import VolatilityEngine


def build_price_history():
    rows = []
    close = 100.0

    for i in range(120):
        close = close * (1.0 + ((-1) ** i) * 0.004)

        rows.append({
            "date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=i),
            "close": close,
        })

    return pd.DataFrame(rows)


def build_option_history():
    rows = []
    iv = 0.25

    for i in range(80):
        iv += 0.001

        rows.append({
            "quote_date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=i),
            "implied_volatility": iv,
        })

    return pd.DataFrame(rows)


def build_option_chain():
    rows = []

    expiries = [
        ("2026-02-06", 7),
        ("2026-02-13", 14),
        ("2026-02-20", 21),
        ("2026-03-06", 35),
        ("2026-03-20", 49),
        ("2026-04-17", 77),
        ("2026-05-15", 105),
    ]

    strikes = [90, 95, 100, 105, 110]

    for expiry, dte in expiries:
        for strike in strikes:
            for option_type in ["CALL", "PUT"]:
                distance = abs(strike - 100)

                base_mid = 2.0 + distance * 0.10 + dte * 0.015

                rows.append({
                    "option_symbol": f"TEST{expiry.replace('-', '')}{option_type[0]}{strike}",
                    "option_type": option_type,
                    "strike": strike,
                    "expiry": expiry,
                    "dte": dte,
                    "bid": round(base_mid - 0.05, 2),
                    "ask": round(base_mid + 0.05, 2),
                    "mid": round(base_mid, 2),
                    "last": round(base_mid, 2),
                    "volume": max(50, 1200 - abs(dte - 35) * 12 - distance * 10),
                    "open_interest": max(100, 4000 - abs(dte - 35) * 20 - distance * 20),
                    "spread_pct": 0.05 if dte <= 60 else 0.12,
                    "delta": 0.50 if option_type == "CALL" else -0.50,
                    "gamma": 0.04,
                    "theta": -0.04 - (1.0 / max(dte, 1)) * 0.10,
                    "vega": 0.25 + dte * 0.003,
                    "rho": 0.04,
                    "implied_volatility": 0.35 + dte * 0.0005,
                })

    return pd.DataFrame(rows)


def print_candidates(title, candidates):
    print(f"\n--- {title} ---")

    for idx, c in enumerate(candidates, start=1):
        warnings = ", ".join(c.warnings) if c.warnings else "-"

        print(
            f"{idx}. Expiry={c.expiry} "
            f"DTE={c.dte:>3} "
            f"Score={c.composite_score:>6.2f} "
            f"DTEscore={c.dte_score:>6.2f} "
            f"Liq={c.liquidity_score:>6.2f} "
            f"Theta={c.theta_score:>6.2f} "
            f"Vol={c.volatility_score:>6.2f} "
            f"Move={c.expected_move_pct:>5.2f}% "
            f"Allowed={c.allowed} "
            f"Warnings={warnings}"
        )


def main():
    prices = build_price_history()
    option_history = build_option_history()
    chain = build_option_chain()

    vol_profile = VolatilityEngine().analyze(
        symbol="TEST",
        price_history=prices,
        option_history=option_history,
    )

    optimizer = ExpirationOptimizer(
        min_contracts_per_expiry=6,
        min_avg_volume=50,
        min_avg_open_interest=100,
        max_avg_spread_pct=0.30,
    )

    print("\n========== Expiration Optimizer Test ==========")
    print(f"Vol Regime : {vol_profile.volatility_regime}")
    print(f"Current IV : {vol_profile.current_iv:.2%}")

    for strategy in [
        "LONG_CALL",
        "LONG_PUT",
        "BULL_PUT_SPREAD",
        "BEAR_CALL_SPREAD",
        "IRON_CONDOR",
    ]:
        candidates = optimizer.optimize(
            symbol="TEST",
            strategy=strategy,
            underlying_price=100.0,
            option_chain=chain,
            volatility_profile=vol_profile,
            top_n=5,
        )

        print_candidates(strategy, candidates)

    print("===============================================")


if __name__ == "__main__":
    main()
