import pandas as pd

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

    iv = 0.20

    for i in range(60):
        iv += 0.002

        rows.append({
            "quote_date": pd.Timestamp("2026-02-01") + pd.Timedelta(days=i),
            "implied_volatility": iv,
        })

    return pd.DataFrame(rows)


def main():
    prices = build_price_history()
    options = build_option_history()

    engine = VolatilityEngine()

    profile = engine.analyze(
        symbol="AAPL",
        price_history=prices,
        option_history=options,
    )

    print("\n========== Volatility Intelligence Test ==========")
    print(f"Symbol              : {profile.symbol}")
    print(f"HV20                : {profile.hv20:.2%}")
    print(f"HV30                : {profile.hv30:.2%}")
    print(f"HV60                : {profile.hv60:.2%}")
    print(f"HV90                : {profile.hv90:.2%}")
    print(f"Current IV          : {profile.current_iv:.2%}")
    print(f"IV Rank             : {profile.iv_rank:.2f}")
    print(f"IV Percentile       : {profile.iv_percentile:.2f}")
    print(f"IV/HV Ratio         : {profile.iv_hv_ratio:.2f}")
    print(f"Vol Regime          : {profile.volatility_regime}")
    print(f"Vol Signal          : {profile.volatility_signal}")
    print(f"Expected Move 1D    : ${profile.expected_move_1d}")
    print(f"Expected Move 5D    : ${profile.expected_move_5d}")
    print(f"Expected Move 10D   : ${profile.expected_move_10d}")
    print(f"Expected Move 30D   : ${profile.expected_move_30d}")
    print(f"Confidence          : {profile.confidence:.2f}")
    print("==================================================")


if __name__ == "__main__":
    main()
