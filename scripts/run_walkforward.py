import argparse
import csv
from pathlib import Path

from trading_ai.walkforward.splitter import WalkForwardSplitter
from trading_ai.walkforward.optimizer import WalkForwardOptimizer
from trading_ai.walkforward.validator import WalkForwardValidator
from trading_ai.optimization.risk_aware_scorer import RiskAwareStrategyScorer


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

    parser.add_argument(
        "--risk-aware",
        action="store_true",
        help="Choose optimization parameters using risk-aware score.",
    )
    parser.add_argument(
        "--risk-summary",
        default="reports/backtest_experiments/summary.csv",
        help="Experiment summary CSV used for risk-aware parameter selection.",
    )
    parser.add_argument(
        "--max-train-drawdown",
        type=float,
        default=None,
        help="Optional training drawdown floor, e.g. -0.30 means reject worse than -30%.",
    )
    parser.add_argument(
        "--min-train-sharpe",
        type=float,
        default=None,
        help="Optional minimum training Sharpe required for selected optimization row.",
    )

    return parser.parse_args()


def safe_float(value, default=0.0):
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default


def read_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def params_from_row(row):
    return {
        "option_premium_pct": safe_float(row.get("option_premium_pct", 0.10)),
        "take_profit": safe_float(row.get("take_profit", 0.03)),
        "stop_loss": safe_float(row.get("stop_loss", -0.02)),
        "max_hold": int(safe_float(row.get("max_hold", 5))),
        "min_delta": safe_float(row.get("min_delta", 0.0)),
        "max_delta": safe_float(row.get("max_delta", 1.0)),
        "min_vega": safe_float(row.get("min_vega", 0.0)),
        "max_vega": safe_float(row.get("max_vega", 999.0)),
        "max_theta": safe_float(row.get("max_theta", 999.0)),
    }


def legacy_best_parameters(profile, min_trades):
    optimizer = WalkForwardOptimizer(
        profile=profile,
        min_trades=min_trades,
    )
    return optimizer.best_parameters(), {}


def risk_aware_best_parameters(args, profile):
    rows = read_rows(args.risk_summary)

    if not rows:
        return legacy_best_parameters(profile, args.min_trades)

    scorer = RiskAwareStrategyScorer(
        profile=profile,
        min_trades=args.min_trades,
    )

    scored_rows = scorer.score_rows(rows)

    if args.max_train_drawdown is not None:
        scored_rows = [
            r for r in scored_rows
            if safe_float(r.get("max_drawdown_pct", 0.0)) >= args.max_train_drawdown
        ]

    if args.min_train_sharpe is not None:
        scored_rows = [
            r for r in scored_rows
            if safe_float(r.get("sharpe_ratio", 0.0)) >= args.min_train_sharpe
        ]

    if not scored_rows:
        return legacy_best_parameters(profile, args.min_trades)

    best = scored_rows[0]
    return params_from_row(best), best


def selected_row_fields(best_row):
    return {
        "risk_score": safe_float(best_row.get("risk_score", 0.0)),
        "risk_grade": best_row.get("risk_grade", ""),
        "risk_reason": best_row.get("risk_reason", ""),
        "train_sharpe": safe_float(best_row.get("sharpe_ratio", 0.0)),
        "train_sortino": safe_float(best_row.get("sortino_ratio", 0.0)),
        "train_max_drawdown_pct": safe_float(best_row.get("max_drawdown_pct", 0.0)),
        "train_return_pct": safe_float(best_row.get("return_pct", 0.0)),
        "train_profit_factor": safe_float(best_row.get("profit_factor", 0.0)),
    }


def main():
    args = parse_args()

    splitter = WalkForwardSplitter(
        start=args.start,
        end=args.end,
        train_months=args.train_months,
        test_months=args.test_months,
        step_months=args.step_months,
    )

    if args.risk_aware:
        primary_params, primary_best = risk_aware_best_parameters(args, args.profile)
    else:
        primary_params, primary_best = legacy_best_parameters(args.profile, args.min_trades)

    fallback_params = None
    fallback_best = {}

    if args.fallback_profile != "none":
        if args.risk_aware:
            fallback_params, fallback_best = risk_aware_best_parameters(
                args,
                args.fallback_profile,
            )
        else:
            fallback_params, fallback_best = legacy_best_parameters(
                args.fallback_profile,
                args.min_trades,
            )

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
    print(f"Risk Aware : {args.risk_aware}")

    for window in splitter.windows():
        print()
        print(
            f"Window {window.index}: "
            f"Train {window.train_start} -> {window.train_end} | "
            f"Test {window.test_start} -> {window.test_end}"
        )

        selected_profile = args.profile
        selected_params = primary_params
        selected_best = primary_best

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
            selected_best = fallback_best

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
            selected_best = {}

            result = validator.validate(
                start=window.test_start,
                end=window.test_end,
                params=selected_params,
            )
            metrics = result["metrics"]

        risk_fields = selected_row_fields(selected_best)

        row = {
            "window": window.index,
            "train_start": window.train_start,
            "train_end": window.train_end,
            "test_start": window.test_start,
            "test_end": window.test_end,
            "option_premium_pct": selected_params["option_premium_pct"],
            "take_profit": selected_params["take_profit"],
            "stop_loss": selected_params["stop_loss"],
            "max_hold": selected_params["max_hold"],
            "trades": metrics["trades"],
            "win_rate": metrics["win_rate"],
            "return_pct": metrics["return_pct"],
            "profit_factor": metrics["profit_factor"],
            "net_pnl": metrics["net_pnl"],
            "run_dir": result["run_dir"],
            "selected_profile": selected_profile,
            "profile": args.profile,
            "min_delta": selected_params.get("min_delta", 0.0),
            "max_delta": selected_params.get("max_delta", 1.0),
            "min_vega": selected_params.get("min_vega", 0.0),
            "max_vega": selected_params.get("max_vega", 999.0),
            "max_theta": selected_params.get("max_theta", 999.0),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
            "max_drawdown_dollars": metrics.get("max_drawdown_dollars", 0.0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
            "sortino_ratio": metrics.get("sortino_ratio", 0.0),
            "calmar_ratio": metrics.get("calmar_ratio", 0.0),
            "payoff_ratio": metrics.get("payoff_ratio", 0.0),
            **risk_fields,
        }

        rows.append(row)

        print(
            f"Profile={selected_profile} | "
            f"RiskScore={safe_float(row.get('risk_score', 0.0)):.2f} | "
            f"Grade={row.get('risk_grade', '')} | "
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
        "risk_score",
        "risk_grade",
        "risk_reason",
        "train_sharpe",
        "train_sortino",
        "train_max_drawdown_pct",
        "train_return_pct",
        "train_profit_factor",
    ]

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total_pnl = sum(float(r["net_pnl"]) for r in rows)
    avg_return = (
        sum(float(r["return_pct"]) for r in rows) / len(rows)
        if rows else 0.0
    )
    avg_pf = (
        sum(float(r["profit_factor"]) for r in rows) / len(rows)
        if rows else 0.0
    )
    avg_sharpe = (
        sum(float(r.get("sharpe_ratio", 0.0)) for r in rows) / len(rows)
        if rows else 0.0
    )
    avg_dd = (
        sum(float(r.get("max_drawdown_pct", 0.0)) for r in rows) / len(rows)
        if rows else 0.0
    )

    print()
    print("========== Walk-Forward Summary ==========")
    print(f"Windows    : {len(rows)}")
    print(f"Total PnL  : ${total_pnl:,.2f}")
    print(f"Avg Return : {avg_return:.2%}")
    print(f"Avg PF     : {avg_pf:.2f}")
    print(f"Avg Sharpe : {avg_sharpe:.2f}")
    print(f"Avg DD     : {avg_dd:.2%}")
    print(f"Summary CSV: {output_file}")
    print("==========================================")
    print()


if __name__ == "__main__":
    main()
