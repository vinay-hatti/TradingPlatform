import argparse
from datetime import datetime
import json
from pathlib import Path
from trading_ai.risk.position_sizer import PositionSizer
from trading_ai.app.bootstrap import container
from trading_ai.backtest.datasource import HistoricalDataSource
from trading_ai.backtest.runner import HistoricalStrategyRunner
from trading_ai.backtest.simulator import OptionTradeSimulator
from trading_ai.backtest.trade_generator import HistoricalTradeGenerator
from trading_ai.backtest.engine import BacktestEngine
from trading_ai.backtest.portfolio import BacktestPortfolio


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
    parser.add_argument("--max-open-positions", type=int, default=5)
    parser.add_argument("--max-position-pct", type=float, default=0.05)
    parser.add_argument("--commission", type=float, default=0.65)
    parser.add_argument("--slippage", type=float, default=0.05)
    parser.add_argument( "--option-premium-pct", type=float, default=0.08)
    parser.add_argument("--risk-per-trade-pct", type=float, default=0.01)
    parser.add_argument("--sizer-max-position-pct", type=float, default=0.10)

    return parser.parse_args()


def main():

    args = parse_args()

    datasource = HistoricalDataSource(container.market)

    simulator = OptionTradeSimulator(
        take_profit_pct=args.take_profit,
        stop_loss_pct=args.stop_loss,
        max_hold_days=args.max_hold,
        commission_per_contract=args.commission,
        slippage_per_contract=args.slippage,
    )

    position_sizer = PositionSizer(
        risk_per_trade_pct=args.risk_per_trade_pct,
        max_position_pct=args.sizer_max_position_pct,
    )

    generator = HistoricalTradeGenerator(
        datasource=datasource,
        simulator=simulator,
        contracts=1,
        max_hold_days=args.max_hold,
        position_sizer=position_sizer,
        capital=args.capital,
        option_premium_pct=args.option_premium_pct,
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

    portfolio = BacktestPortfolio(
        initial_capital=args.capital,
        max_open_positions=args.max_open_positions,
        max_position_pct=args.max_position_pct,
    )

    portfolio_result = portfolio.process_trades(all_trades)

    trades = portfolio_result["closed_trades"]
    rejected_trades = portfolio_result["rejected"]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_symbols = "_".join(symbols)
    run_dir = f"reports/backtests/{timestamp}_{safe_symbols}"

    Path(run_dir).mkdir(parents=True, exist_ok=True)

    config = {
        "symbols": symbols,
        "start": args.start,
        "end": args.end,
        "capital": args.capital,
        "min_score": args.min_score,
        "take_profit": args.take_profit,
        "stop_loss": args.stop_loss,
        "max_hold": args.max_hold,
        "max_open_positions": args.max_open_positions,
        "max_position_pct": args.max_position_pct,
        "commission": args.commission,
        "slippage": args.slippage,
        "risk_per_trade_pct": args.risk_per_trade_pct,
        "sizer_max_position_pct": args.sizer_max_position_pct,
        "option_premium_pct": args.option_premium_pct,
    }

    with open(f"{run_dir}/config.json", "w") as f:
        json.dump(config, f, indent=2)

    report_path = f"{run_dir}/report.html"

    result = BacktestEngine(
        initial_capital=args.capital,
    ).run(
        trades,
        report_path=report_path,
        rejected=rejected_trades,
    )

    metrics = result["metrics"]

    print()
    print("========== Historical Backtest ==========")
    print(f"Symbols       : {', '.join(symbols)}")
    print(f"Period        : {args.start} -> {args.end}")
    print(f"Trading Days  : {total_trading_days}")
    print(f"Signals       : {total_signals}")
    print(f"Trades        : {len(trades)}")
    print(f"Accepted      : {len(trades)}")
    print(f"Rejected      : {len(rejected_trades)}")

    rejected_by_reason = {}

    for item in rejected_trades:
        reason = item["reason"]
        rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1

    if rejected_by_reason:
        print("Rejected By Reason:")

        for reason, count in sorted(rejected_by_reason.items()):
            print(f"  {reason:22}: {count}")

    total_fees = sum(float(t.fees) for t in trades)
    gross_pnl = sum(float(t.gross_pnl) for t in trades)

    print(f"Gross PnL     : ${gross_pnl:,.2f}")
    print(f"Fees          : ${total_fees:,.2f}")
    print(f"Net PnL       : ${metrics['net_pnl']:,.2f}")
    print(f"Win Rate      : {metrics['win_rate']:.2%}")
    print(f"Return        : {metrics['return_pct']:.2%}")
    print(f"Profit Factor : {metrics['profit_factor']:.2f}")
    print(f"Expectancy    : ${metrics['expectancy']:,.2f}")
    print(f"Report        : {result['report_path']}")
    print("=========================================")
    print()


if __name__ == "__main__":
    main()
