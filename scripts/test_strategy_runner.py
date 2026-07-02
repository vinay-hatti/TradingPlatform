from trading_ai.app.bootstrap import container
from trading_ai.backtest.datasource import HistoricalDataSource
from trading_ai.backtest.runner import HistoricalStrategyRunner


def main():

    datasource = HistoricalDataSource(container.market)

    runner = HistoricalStrategyRunner(
        datasource=datasource,
        feature_pipeline=container.pipeline,
    )

    signals = runner.run(
        symbol="AAPL",
        start_date="2026-01-01",
        end_date="2026-06-01",
    )

    df = datasource.get_price_history(
        "AAPL",
        "2026-01-01",
        "2026-06-01",
    )

    print()
    print("========== Historical Strategy Runner ==========")
    print(f"Trading Days : {len(df)}")
    print(f"Signals      : {len(signals)}")
    print()

    for signal in signals[:10]:
        print(
            f"{signal['date']} | "
            f"{signal['symbol']:5} | "
            f"{signal['signal']:4} | "
            f"Score={float(signal['score']):6.2f} | "
            f"Call={float(signal['call_score']):6.2f} | "
            f"Put={float(signal['put_score']):6.2f} | "
            f"Regime={signal['regime']} | "
            f"Close={float(signal['close']):8.2f}"
        )

    print("================================================")
    print()


if __name__ == "__main__":
    main()
