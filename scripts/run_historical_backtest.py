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

    parser.add_argument("--symbol", default="AAPL")
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

    price_history = datasource.get_price_history(
        args.symbol,
        args.start,
        args.end,
    )

    runner = HistoricalStrategyRunner(
        datasource=datasource,
        feature_pipeline=container.pipeline,
        min_score=args.min_score,
    )

    signals = runner.run(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
    )

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

    trades = generator.generate(
        signals=signals,
        price_history=price_history,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path = (
        f"reports/backtest_{args.symbol}_{timestamp}.html"
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
    print(f"Symbol        : {args.symbol}")
    print(f"Period        : {args.start} -> {args.end}")
    print(f"Trading Days  : {len(price_history)}")
    print(f"Signals       : {len(signals)}")
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
