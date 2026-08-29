from trading_ai.app.bootstrap import container
from trading_ai.backtest.datasource import HistoricalDataSource


def main():

    ds = HistoricalDataSource(container.market)

    df = ds.get_price_history(
        "AAPL",
        "2026-01-01",
        "2026-06-01",
    )

    print()
    print("========== Historical Data Source Test ==========")
    print(f"Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")

    dates = ds.get_trading_dates(df)
    print(f"Trading Dates: {len(dates)}")

    if dates:
        future = ds.get_next_days(
            df,
            dates[-15],
            days=5,
        )

        print("Future Days:")
        for row in future:
            print(row)

    print("================================================")
    print()


if __name__ == "__main__":
    main()
