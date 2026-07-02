import argparse
from datetime import datetime

from trading_ai.app.bootstrap import container
from trading_ai.backtest.datasource import HistoricalDataSource
from trading_ai.backtest.runner import HistoricalStrategyRunner
from trading_ai.backtest.simulator import OptionTradeSimulator
from trading_ai.backtest.trade_generator import HistoricalTradeGenerator
from trading_ai.backtest.engine import BacktestEngine


def parse_args():

    parser = argparse.ArgumentParser(
        description="Run historical strategy backtest"
    )

    parser.add_argument("--symbols", default="AAPL")
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-06-01")
    parser.add_argument("--capital", type=float, default=100000.0)
    parser.add_argument("--min-score", type=float, default=60.0)
    parser.add_argument("--take-profit", type=float, default=0.05)
    parser.add_argument("--stop-loss", type=float, default=-0.03)
    parser.add_argument("--max-hold", type=int, default=10)

    return parser.parse_args()


def main():

    args = parse_args()

    datasource = HistoricalDataSource(container.market)

    simulator = OptionTradeSimulator(
        take_profit_pct=args.take_profit,
        stop_loss_pct=args.stop_loss,
        max_hold_days=args.max_hold,
    )

    generator = HistoricalTradeGenerator(
        datasource=datasource,
        simulator=simulator,
        contracts=1,
        max_hold_days=args.max_hold,
    )

    symbols = [
        s.strip().upper()
        for s in args.symbols.split(",")
        if s.strip()
    ]

    all_trades = []
    total_trading_days = 0
    total_signals = 0

    for symbol in symbols:
        price_history = datasource.get_price_history(
            symbol,
            args.start,
            args.end,
        )

        total_trading_days += len(price_history)

        runner = HistoricalStrategyRunner(
            datasource=datasource,
            feature_pipeline=container.pipeline,
            min_score=args.min_score,
        )

        signals = runner.run(
            symbol=symbol,
            start_date=args.start,
            end_date=args.end,
        )

        total_signals += len(signals)

        trades = generator.generate(
            signals=signals,
            price_history=price_history,
        )

        all_trades.extend(trades)

    trades = all_trades



    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path = (
        f"reports/backtest_multi_{timestamp}.html"
    )

    result = BacktestEngine(
        initial_capital=args.capital,
    ).run(
        trades,
        report_path=report_path,
    )

    metrics = result["metrics"]

    print()
    print("========== Historical Backtest ==========")
    print(f"Symbols       : {', '.join(symbols)}")
    print(f"Period        : {args.start} -> {args.end}")
    print(f"Trading Days  : {total_trading_days}")
    print(f"Signals       : {total_signals}")
    print(f"Trades        : {len(trades)}")
    print(f"Win Rate      : {metrics['win_rate']:.2%}")
    print(f"Net PnL       : ${metrics['net_pnl']:,.2f}")
    print(f"Return        : {metrics['return_pct']:.2%}")
    print(f"Profit Factor : {metrics['profit_factor']:.2f}")
    print(f"Expectancy    : ${metrics['expectancy']:,.2f}")
    print(f"Report        : {result['report_path']}")
    print("=========================================")
    print()


if __name__ == "__main__":
    main()
