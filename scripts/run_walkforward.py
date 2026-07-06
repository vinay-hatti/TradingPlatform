import argparse
import csv
from pathlib import Path

from trading_ai.walkforward.splitter import WalkForwardSplitter
from trading_ai.walkforward.optimizer import WalkForwardOptimizer
from trading_ai.walkforward.validator import WalkForwardValidator


def parse_args():

    parser = argparse.ArgumentParser(
        description="Run walk-forward validation"
    )

    parser.add_argument("--symbols", default="AAPL,MSFT,AMZN")
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-06-01")
    parser.add_argument("--train-months", type=int, default=2)
    parser.add_argument("--test-months", type=int, default=1)
    parser.add_argument("--step-months", type=int, default=1)

    return parser.parse_args()


def main():

    args = parse_args()

    splitter = WalkForwardSplitter(
        start=args.start,
        end=args.end,
        train_months=args.train_months,
        test_months=args.test_months,
        step_months=args.step_months,
    )

    optimizer = WalkForwardOptimizer()

    params = optimizer.best_parameters()

    validator = WalkForwardValidator(
        symbols=args.symbols,
    )

    rows = []

    print()
    print("========== Walk-Forward Run ==========")

    for window in splitter.windows():

        print()
        print(
            f"Window {window.index}: "
            f"Train {window.train_start} -> {window.train_end} | "
            f"Test {window.test_start} -> {window.test_end}"
        )

        result = validator.validate(
            start=window.test_start,
            end=window.test_end,
            params=params,
        )

        metrics = result["metrics"]

        rows.append({
            "window": window.index,
            "train_start": window.train_start,
            "train_end": window.train_end,
            "test_start": window.test_start,
            "test_end": window.test_end,
            "option_premium_pct": params["option_premium_pct"],
            "take_profit": params["take_profit"],
            "stop_loss": params["stop_loss"],
            "max_hold": params["max_hold"],
            "trades": metrics["trades"],
            "win_rate": metrics["win_rate"],
            "return_pct": metrics["return_pct"],
            "profit_factor": metrics["profit_factor"],
            "net_pnl": metrics["net_pnl"],
            "run_dir": result["run_dir"],
        })

        print(
            f"Trades={metrics['trades']} | "
            f"Return={metrics['return_pct']:.2%} | "
            f"PF={metrics['profit_factor']:.2f} | "
            f"PnL=${metrics['net_pnl']:,.2f}"
        )

    output_dir = Path("reports/walkforward")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "summary.csv"

    fieldnames = [
        "window",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "option_premium_pct",
        "take_profit",
        "stop_loss",
        "max_hold",
        "trades",
        "win_rate",
        "return_pct",
        "profit_factor",
        "net_pnl",
        "run_dir",
    ]

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total_pnl = sum(float(r["net_pnl"]) for r in rows)
    avg_return = (
        sum(float(r["return_pct"]) for r in rows) / len(rows)
        if rows
        else 0.0
    )
    avg_pf = (
        sum(float(r["profit_factor"]) for r in rows) / len(rows)
        if rows
        else 0.0
    )

    print()
    print("========== Walk-Forward Summary ==========")
    print(f"Windows    : {len(rows)}")
    print(f"Total PnL  : ${total_pnl:,.2f}")
    print(f"Avg Return : {avg_return:.2%}")
    print(f"Avg PF     : {avg_pf:.2f}")
    print(f"Summary CSV: {output_file}")
    print("==========================================")
    print()


if __name__ == "__main__":
    main()
