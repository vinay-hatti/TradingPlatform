import pandas as pd

from trading_ai.strategy_engine.strategy_selector import StrategySelector
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


def build_high_iv_history():
    rows = []
    iv = 0.20

    for i in range(60):
        iv += 0.003

        rows.append({
            "quote_date": pd.Timestamp("2026-02-01") + pd.Timedelta(days=i),
            "implied_volatility": iv,
        })

    return pd.DataFrame(rows)


def build_low_iv_history():
    rows = []
    iv = 0.45

    for i in range(60):
        iv -= 0.003

        rows.append({
            "quote_date": pd.Timestamp("2026-02-01") + pd.Timedelta(days=i),
            "implied_volatility": max(iv, 0.10),
        })

    return pd.DataFrame(rows)


def print_candidates(title, candidates):
    print(f"\n========== {title} ==========")

    for idx, c in enumerate(candidates, start=1):
        warnings = ", ".join(c.warnings) if c.warnings else "-"

        print(
            f"{idx}. {c.strategy:<22} "
            f"Score={c.score:>6.2f} | "
            f"Allowed={c.allowed} | "
            f"Risk={c.risk_profile:<14} | "
            f"Premium={c.premium_type:<6} | "
            f"Reason={c.reason} | "
            f"Warnings={warnings}"
        )


def main():
    prices = build_price_history()

    vol_engine = VolatilityEngine()
    selector = StrategySelector()

    high_iv_profile = vol_engine.analyze(
        symbol="AAPL",
        price_history=prices,
        option_history=build_high_iv_history(),
    )

    low_iv_profile = vol_engine.analyze(
        symbol="AAPL",
        price_history=prices,
        option_history=build_low_iv_history(),
    )

    bullish_high_iv = selector.select(
        symbol="AAPL",
        direction="CALL",
        market_regime="BULL_TREND",
        volatility_profile=high_iv_profile,
    )

    bearish_low_iv = selector.select(
        symbol="AAPL",
        direction="PUT",
        market_regime="BEAR_TREND",
        volatility_profile=low_iv_profile,
    )

    neutral_high_iv = selector.select(
        symbol="AAPL",
        direction="NEUTRAL",
        market_regime="SIDEWAYS",
        volatility_profile=high_iv_profile,
    )

    print("\n========== Strategy Selector Test ==========")
    print(f"High IV Regime : {high_iv_profile.volatility_regime}")
    print(f"Low IV Regime  : {low_iv_profile.volatility_regime}")

    print_candidates("Bullish / High IV", bullish_high_iv)
    print_candidates("Bearish / Low IV", bearish_low_iv)
    print_candidates("Neutral / High IV", neutral_high_iv)

    print("\nBest bullish/high-IV strategy:")
    best = selector.best(
        symbol="AAPL",
        direction="CALL",
        market_regime="BULL_TREND",
        volatility_profile=high_iv_profile,
    )

    if best:
        print(f"{best.strategy} | Score={best.score:.2f} | Reason={best.reason}")

    print("============================================")


if __name__ == "__main__":
    main()
