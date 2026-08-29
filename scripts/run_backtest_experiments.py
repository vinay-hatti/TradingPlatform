import argparse
import csv
import itertools
import json
import subprocess
from pathlib import Path


def parse_float_list(value):
    return [float(v.strip()) for v in value.split(",") if v.strip()]


def latest_backtest_dir():
    dirs = sorted(
        Path("reports/backtests").glob("*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return dirs[0] if dirs else None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run backtest parameter experiments"
    )

    parser.add_argument("--symbols", default="AAPL,MSFT,AMZN")
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-06-01")
    parser.add_argument("--capital", type=float, default=100000.0)

    parser.add_argument("--pricing-dte", type=int, default=30)
    parser.add_argument("--risk-free-rate", type=float, default=0.04)

    parser.add_argument("--option-premium-pct", default="0.05,0.08,0.12")
    parser.add_argument("--take-profit", default="0.05")
    parser.add_argument("--stop-loss", default="-0.03")
    parser.add_argument("--max-hold", default="10")

    parser.add_argument("--max-position-pct", type=float, default=0.05)
    parser.add_argument("--risk-per-trade-pct", type=float, default=0.05)
    parser.add_argument("--sizer-max-position-pct", type=float, default=0.05)

    parser.add_argument("--min-delta", default="0.0")
    parser.add_argument("--max-delta", default="1.0")
    parser.add_argument("--min-vega", default="0.0")
    parser.add_argument("--max-vega", default="999.0")
    parser.add_argument("--max-theta", default="999.0")

    parser.add_argument("--use-historical-options", action="store_true")
    parser.add_argument("--no-bs-fallback", action="store_true")

    parser.add_argument("--min-option-volume", type=int, default=0)
    parser.add_argument("--min-open-interest", type=int, default=0)
    parser.add_argument("--max-spread-pct", type=float, default=1.0)

    return parser.parse_args()


def main():
    args = parse_args()

    option_premiums = parse_float_list(args.option_premium_pct)
    take_profits = parse_float_list(args.take_profit)
    stop_losses = parse_float_list(args.stop_loss)
    max_holds = [int(v.strip()) for v in args.max_hold.split(",") if v.strip()]
    min_deltas = parse_float_list(args.min_delta)
    max_deltas = parse_float_list(args.max_delta)
    min_vegas = parse_float_list(args.min_vega)
    max_vegas = parse_float_list(args.max_vega)
    max_thetas = parse_float_list(args.max_theta)

    combos = list(
        itertools.product(
            option_premiums,
            take_profits,
            stop_losses,
            max_holds,
            min_deltas,
            max_deltas,
            min_vegas,
            max_vegas,
            max_thetas,
        )
    )

    summary_rows = []

    print()
    print("========== Backtest Experiments ==========")
    print(f"Total Runs: {len(combos)}")
    print("==========================================")
    print()

    for idx, combo in enumerate(combos, start=1):
        (
            option_premium_pct,
            take_profit,
            stop_loss,
            max_hold,
            min_delta,
            max_delta,
            min_vega,
            max_vega,
            max_theta,
        ) = combo

        print(
            f"Run {idx}/{len(combos)} | "
            f"premium={option_premium_pct} | "
            f"tp={take_profit} | "
            f"sl={stop_loss} | "
            f"hold={max_hold}"
        )

        cmd = [
            "uv", "run", "python", "-m", "trading_ai", "backtest",
            "--symbols", args.symbols,
            "--start", args.start,
            "--end", args.end,
            "--capital", str(args.capital),
            "--pricing-dte", str(args.pricing_dte),
            "--risk-free-rate", str(args.risk_free_rate),
            "--max-position-pct", str(args.max_position_pct),
            "--risk-per-trade-pct", str(args.risk_per_trade_pct),
            "--sizer-max-position-pct", str(args.sizer_max_position_pct),
            "--option-premium-pct", str(option_premium_pct),
            "--take-profit", str(take_profit),
            "--stop-loss", str(stop_loss),
            "--max-hold", str(max_hold),
            "--min-delta", str(min_delta),
            "--max-delta", str(max_delta),
            "--min-vega", str(min_vega),
            "--max-vega", str(max_vega),
            "--max-theta", str(max_theta),
            "--min-option-volume", str(args.min_option_volume),
            "--min-open-interest", str(args.min_open_interest),
            "--max-spread-pct", str(args.max_spread_pct),
        ]

        if args.use_historical_options:
            cmd.append("--use-historical-options")

        if args.no_bs_fallback:
            cmd.append("--no-bs-fallback")

        subprocess.run(cmd, check=True)

        run_dir = latest_backtest_dir()
        if run_dir is None:
            raise RuntimeError("No backtest report directory found.")

        with open(run_dir / "metrics.json", "r") as f:
            metrics = json.load(f)

        with open(run_dir / "config.json", "r") as f:
            config = json.load(f)

        summary_rows.append({
            "run": idx,
            "run_dir": str(run_dir),
            "symbols": ",".join(config["symbols"]),
            "start": config["start"],
            "end": config["end"],
            "pricing_dte": config.get("pricing_dte", args.pricing_dte),
            "risk_free_rate": config.get("risk_free_rate", args.risk_free_rate),
            "option_premium_pct": config["option_premium_pct"],
            "take_profit": config["take_profit"],
            "stop_loss": config["stop_loss"],
            "max_hold": config["max_hold"],
            "trades": metrics["trades"],
            "wins": metrics["wins"],
            "losses": metrics["losses"],
            "win_rate": metrics["win_rate"],
            "net_pnl": metrics["net_pnl"],
            "return_pct": metrics["return_pct"],
            "profit_factor": metrics["profit_factor"],
            "expectancy": metrics["expectancy"],
            "min_delta": config.get("min_delta", min_delta),
            "max_delta": config.get("max_delta", max_delta),
            "min_vega": config.get("min_vega", min_vega),
            "max_vega": config.get("max_vega", max_vega),
            "max_theta": config.get("max_theta", max_theta),
            "use_historical_options": config.get("use_historical_options", args.use_historical_options),
            "fallback_to_black_scholes": config.get("fallback_to_black_scholes", not args.no_bs_fallback),
            "min_option_volume": config.get("min_option_volume", args.min_option_volume),
            "min_open_interest": config.get("min_open_interest", args.min_open_interest),
            "max_spread_pct": config.get("max_spread_pct", args.max_spread_pct),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
            "max_drawdown_dollars": metrics.get("max_drawdown_dollars", 0.0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
            "sortino_ratio": metrics.get("sortino_ratio", 0.0),
            "calmar_ratio": metrics.get("calmar_ratio", 0.0),
            "payoff_ratio": metrics.get("payoff_ratio", 0.0),
        })

    output_dir = Path("reports/backtest_experiments")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "summary.csv"

    fieldnames = list(summary_rows[0].keys()) if summary_rows else []

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    ranked = sorted(
        summary_rows,
        key=lambda r: (
            float(r["profit_factor"]),
            float(r["return_pct"]),
        ),
        reverse=True,
    )

    print()
    print("========== Experiment Summary ==========")

    for row in ranked:
        print(
            f"Run={row['run']:>3} | "
            f"DTE={int(row['pricing_dte']):>2} | "
            f"RFR={float(row['risk_free_rate']):.2%} | "
            f"Prem={float(row['option_premium_pct']):.2%} | "
            f"TP={float(row['take_profit']):.2%} | "
            f"SL={float(row['stop_loss']):.2%} | "
            f"Hold={row['max_hold']:>2} | "
            f"Trades={row['trades']:>3} | "
            f"Return={float(row['return_pct']):7.2%} | "
            f"PF={float(row['profit_factor']):5.2f} | "
            f"Sharpe={float(row.get('sharpe_ratio', 0.0)):5.2f} | "
            f"DD={float(row.get('max_drawdown_pct', 0.0)):7.2%} | "
            f"PnL=${float(row['net_pnl']):,.2f}"
        )

    print(f"Summary CSV: {output_file}")
    print("========================================")
    print()


if __name__ == "__main__":
    main()
