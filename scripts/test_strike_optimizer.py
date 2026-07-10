import pandas as pd

from trading_ai.strategy_engine.strike_optimizer import StrikeOptimizer


def build_option_chain():
    rows = []

    underlying = 100.0

    for strike in [85, 90, 95, 100, 105, 110, 115]:
        call_mid = max(underlying - strike, 0) + 2.0 + abs(strike - underlying) * 0.05
        put_mid = max(strike - underlying, 0) + 2.0 + abs(strike - underlying) * 0.05

        rows.append({
            "option_symbol": f"TESTC{strike}",
            "option_type": "CALL",
            "strike": strike,
            "expiry": "2026-02-20",
            "dte": 30,
            "bid": round(call_mid - 0.05, 2),
            "ask": round(call_mid + 0.05, 2),
            "mid": round(call_mid, 2),
            "last": round(call_mid, 2),
            "volume": 1000 - abs(strike - 100) * 20,
            "open_interest": 3000 - abs(strike - 100) * 30,
            "spread_pct": 0.05,
            "delta": max(min(0.50 - ((strike - 100) * 0.04), 0.95), 0.05),
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
            "bid": round(put_mid - 0.05, 2),
            "ask": round(put_mid + 0.05, 2),
            "mid": round(put_mid, 2),
            "last": round(put_mid, 2),
            "volume": 1000 - abs(strike - 100) * 20,
            "open_interest": 3000 - abs(strike - 100) * 30,
            "spread_pct": 0.05,
            "delta": -max(min(0.50 + ((strike - 100) * 0.04), 0.95), 0.05),
            "gamma": 0.04,
            "theta": -0.05,
            "vega": 0.30,
            "rho": -0.05,
            "implied_volatility": 0.35,
        })

    return pd.DataFrame(rows)


def print_single(candidates):
    for idx, c in enumerate(candidates, start=1):
        warnings = ", ".join(c.warnings) if c.warnings else "-"

        print(
            f"{idx}. {c.strategy:<18} "
            f"{c.option_type:<4} "
            f"Strike={c.strike:>7.2f} "
            f"Score={c.composite_score:>6.2f} "
            f"Liq={c.liquidity_score:>6.2f} "
            f"Greek={c.greek_score:>6.2f} "
            f"Money={c.moneyness_score:>6.2f} "
            f"Allowed={c.allowed} "
            f"Warnings={warnings}"
        )


def print_spreads(candidates):
    for idx, c in enumerate(candidates, start=1):
        warnings = ", ".join(c.warnings) if c.warnings else "-"

        print(
            f"{idx}. {c.strategy:<18} "
            f"Short={c.short_strike:>7.2f} "
            f"Long={c.long_strike:>7.2f} "
            f"Credit/Debit={c.credit_or_debit:>6.2f} "
            f"MaxProfit={c.max_profit:>8.2f} "
            f"MaxLoss={c.max_loss:>8.2f} "
            f"Score={c.composite_score:>6.2f} "
            f"Allowed={c.allowed} "
            f"Warnings={warnings}"
        )


def main():
    chain = build_option_chain()

    optimizer = StrikeOptimizer(
        min_volume=100,
        min_open_interest=500,
        max_spread_pct=0.20,
    )

    print("\n========== Strike Optimizer Test ==========")

    print("\n--- LONG_CALL ---")
    long_call = optimizer.optimize(
        symbol="TEST",
        strategy="LONG_CALL",
        underlying_price=100.0,
        option_chain=chain,
        top_n=5,
    )
    print_single(long_call)

    print("\n--- LONG_PUT ---")
    long_put = optimizer.optimize(
        symbol="TEST",
        strategy="LONG_PUT",
        underlying_price=100.0,
        option_chain=chain,
        top_n=5,
    )
    print_single(long_put)

    print("\n--- BULL_PUT_SPREAD ---")
    bull_put = optimizer.optimize(
        symbol="TEST",
        strategy="BULL_PUT_SPREAD",
        underlying_price=100.0,
        option_chain=chain,
        top_n=5,
    )
    print_spreads(bull_put)

    print("\n--- BEAR_CALL_SPREAD ---")
    bear_call = optimizer.optimize(
        symbol="TEST",
        strategy="BEAR_CALL_SPREAD",
        underlying_price=100.0,
        option_chain=chain,
        top_n=5,
    )
    print_spreads(bear_call)

    print("===========================================")


if __name__ == "__main__":
    main()
