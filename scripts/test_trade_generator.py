from trading_ai.app.bootstrap import container
from trading_ai.backtest.datasource import HistoricalDataSource
from trading_ai.backtest.runner import HistoricalStrategyRunner
from trading_ai.backtest.simulator import OptionTradeSimulator
from trading_ai.backtest.trade_generator import HistoricalTradeGenerator
from trading_ai.backtest.engine import BacktestEngine


def main():

    symbol = "AAPL"
    start = "2026-01-01"
    end = "2026-06-01"

    datasource = HistoricalDataSource(container.market)

    price_history = datasource.get_price_history(
        symbol,
        start,
        end,
    )

    runner = HistoricalStrategyRunner(
        datasource=datasource,
        feature_pipeline=container.pipeline,
        min_score=60,
    )

    signals = runner.run(
        symbol=symbol,
        start_date=start,
        end_date=end,
    )

    simulator = OptionTradeSimulator(
        take_profit_pct=0.05,
        stop_loss_pct=-0.03,
        max_hold_days=10,
    )

    generator = HistoricalTradeGenerator(
        datasource=datasource,
        simulator=simulator,
        contracts=1,
        max_hold_days=10,
    )

    trades = generator.generate(
        signals=signals,
        price_history=price_history,
    )

    result = BacktestEngine(
        initial_capital=100000.0,
    ).run(
        trades,
        report_path="reports/historical_trade_generator_test.html",
    )

    print()
    print("========== Historical Trade Generator ==========")
    print(f"Trading Days : {len(price_history)}")
    print(f"Signals      : {len(signals)}")
    print(f"Trades       : {len(trades)}")
    print()

    if trades:
        first = trades[0]
        last = trades[-1]

        print("First Trade:")
        print(first)
        print()

        print("Last Trade:")
        print(last)
        print()

    metrics = result["metrics"]

    print("Metrics:")
    print(f"Win Rate      : {metrics['win_rate']:.2%}")
    print(f"Net PnL       : ${metrics['net_pnl']:,.2f}")
    print(f"Return        : {metrics['return_pct']:.2%}")
    print(f"Profit Factor : {metrics['profit_factor']:.2f}")
    print(f"Report        : {result['report_path']}")
    print("================================================")
    print()


if __name__ == "__main__":
    main()
