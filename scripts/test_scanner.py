import argparse

from trading_ai.app.bootstrap import container
from trading_ai.backtest.engine import BacktestEngine
from trading_ai.backtest.report import BacktestReport
from trading_ai.backtest.config import BacktestConfig


def parse_args():

    parser = argparse.ArgumentParser(
        description="Run Trading AI backtest"
    )

    parser.add_argument(
        "--symbols",
        default="AAPL,MSFT",
        help="Comma-separated symbols, example: AAPL,MSFT,NVDA",
    )

    parser.add_argument(
        "--start",
        default="2026-01-01",
        help="Backtest start date YYYY-MM-DD",
    )

    parser.add_argument(
        "--end",
        default="2026-06-01",
        help="Backtest end date YYYY-MM-DD",
    )

    parser.add_argument(
        "--stop-loss",
        type=float,
        default=-0.08,
    )

    parser.add_argument(
        "--take-profit",
        type=float,
        default=0.15,
    )

    parser.add_argument(
        "--max-hold",
        type=int,
        default=10,
    )

    return parser.parse_args()


def main():

    args = parse_args()

    config = BacktestConfig(
        symbols=[
            s.strip().upper()
            for s in args.symbols.split(",")
            if s.strip()
        ],
        start=args.start,
        end=args.end,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        max_holding_bars=args.max_hold,
        initial_capital=100000.0,
        risk_per_trade_pct=0.01,
        max_contracts=5,
        min_call_score=60.0,
        min_put_score=60.0,
        min_option_price=0.50,
        min_abs_delta=0.30,
        max_abs_delta=0.70,
        allowed_regimes=None,
        allowed_strategies=None,
        max_open_positions=2,
        max_daily_loss_pct=0.03,
    )

    engine = BacktestEngine(
        container.strategy_engine,
        container.market,
        container.pipeline,
        config=config,
    )

    results = engine.run(
        symbols=config.symbols,
        start=config.start,
        end=config.end,
    )

    report = BacktestReport()
    report.print(results)
    report.export_closed_trades_csv(results)
    report.export_equity_curve_csv(results)
    report.export_equity_curve_chart(results)


if __name__ == "__main__":
    main()
