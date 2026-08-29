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
    parser.add_argument(
        "--profile",
        choices=["conservative", "balanced", "aggressive"],
        default="balanced",
    )
    parser.add_argument("--min-trades", type=int, default=10)
    parser.add_argument(
        "--fallback-profile",
        choices=["conservative", "balanced", "aggressive", "none"],
        default="none",
    )
    parser.add_argument("--min-test-trades", type=int, default=1)
    parser.add_argument(
        "--final-fallback-unfiltered",
        action="store_true",
    )
    parser.add_argument(
        "--output-name",
        default="summary",
    )

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

    primary_optimizer = WalkForwardOptimizer(
        profile=args.profile,
        min_trades=args.min_trades,
    )

    primary_params = primary_optimizer.best_parameters()

    fallback_params = None

    if args.fallback_profile != "none":
        fallback_optimizer = WalkForwardOptimizer(
            profile=args.fallback_profile,
            min_trades=args.min_trades,
        )

        fallback_params = fallback_optimizer.best_parameters()

    unfiltered_params = dict(primary_params)
    unfiltered_params.update({
        "min_delta": 0.0,
        "max_delta": 1.0,
        "min_vega": 0.0,
        "max_vega": 999.0,
        "max_theta": 999.0,
    })

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

        selected_profile = args.profile
        selected_params = primary_params

        result = validator.validate(
            start=window.test_start,
            end=window.test_end,
            params=selected_params,
        )

        metrics = result["metrics"]

        if (
            int(metrics["trades"]) < args.min_test_trades
            and fallback_params is not None
        ):
            selected_profile = args.fallback_profile
            selected_params = fallback_params

            result = validator.validate(
                start=window.test_start,
                end=window.test_end,
                params=selected_params,
            )

            metrics = result["metrics"]

        if (
            int(metrics["trades"]) < args.min_test_trades
            and args.final_fallback_unfiltered
        ):
            selected_profile = "unfiltered"
            selected_params = unfiltered_params

            result = validator.validate(
                start=window.test_start,
                end=window.test_end,
                params=selected_params,
            )

            metrics = result["metrics"]


#        metrics = result["metrics"]

        rows.append({
            "window": window.index,
            "train_start": window.train_start,
            "train_end": window.train_end,
            "test_start": window.test_start,
            "test_end": window.test_end,
            "option_premium_pct": selected_params["option_premium_pct"],
            "take_profit": selected_params["take_profit"],
            "stop_loss": selected_params["stop_loss"],
            "max_hold": selected_params["max_hold"],
            "min_delta": selected_params.get("min_delta", 0.0),
            "max_delta": selected_params.get("max_delta", 1.0),
            "min_vega": selected_params.get("min_vega", 0.0),
            "max_vega": selected_params.get("max_vega", 999.0),
            "max_theta": selected_params.get("max_theta", 999.0),
            "trades": metrics["trades"],
            "win_rate": metrics["win_rate"],
            "return_pct": metrics["return_pct"],
            "profit_factor": metrics["profit_factor"],
            "net_pnl": metrics["net_pnl"],
            "run_dir": result["run_dir"],
            "profile": args.profile,
            "selected_profile": selected_profile,
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
            "max_drawdown_dollars": metrics.get("max_drawdown_dollars", 0.0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
            "sortino_ratio": metrics.get("sortino_ratio", 0.0),
            "calmar_ratio": metrics.get("calmar_ratio", 0.0),
            "payoff_ratio": metrics.get("payoff_ratio", 0.0),
        })

        print(
            f"Profile={selected_profile} | "
            f"Trades={metrics['trades']} | "
            f"Return={metrics['return_pct']:.2%} | "
            f"PF={metrics['profit_factor']:.2f} | "
            f"Sharpe={metrics.get('sharpe_ratio', 0.0):.2f} | "
            f"DD={metrics.get('max_drawdown_pct', 0.0):.2%} | "
            f"PnL=${metrics['net_pnl']:,.2f}"
        )

    output_dir = Path("reports/walkforward")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{args.output_name}.csv"

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
        "selected_profile",
        "profile",
        "min_delta",
        "max_delta",
        "min_vega",
        "max_vega",
        "max_theta",
        "max_drawdown_pct",
        "max_drawdown_dollars",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "payoff_ratio",
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
