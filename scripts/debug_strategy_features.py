from trading_ai.app.bootstrap import container
from trading_ai.backtest.datasource import HistoricalDataSource


def main():

    datasource = HistoricalDataSource(container.market)

    df = datasource.get_price_history(
        "AAPL",
        "2026-01-01",
        "2026-06-01",
    )

    features = container.pipeline.run(df)

    print()
    print("========== Strategy Feature Debug ==========")
    print(f"Rows: {len(features)}")
    print("Columns:")
    for c in features.columns:
        print(f"  {c}")

    print()
    print("Signal value counts:")
    if "signal" in features.columns:
        print(features["signal"].value_counts(dropna=False))
    else:
        print("No signal column found")

    print()
    print("Last 10 rows:")
    cols = [
        c for c in [
            "time",
            "close",
            "signal",
            "market_regime",
            "call_score",
            "put_score",
            "rsi14",
            "macd",
            "macd_signal",
        ]
        if c in features.columns
    ]

    print(features[cols].tail(10).to_string())

    print("============================================")
    print()


if __name__ == "__main__":
    main()
