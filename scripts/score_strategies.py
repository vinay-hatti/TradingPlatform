import argparse
import csv
from pathlib import Path

from trading_ai.optimization.strategy_scorer import StrategyScorer
from trading_ai.optimization.risk_aware_scorer import RiskAwareStrategyScorer


def parse_args():
    parser = argparse.ArgumentParser(
        description="Score and rank strategy experiment results"
    )

    parser.add_argument(
        "--summary",
        default="reports/backtest_experiments/summary.csv",
    )
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--min-trades", type=int, default=10)
    parser.add_argument(
        "--profile",
        choices=["conservative", "balanced", "aggressive"],
        default="balanced",
    )
    parser.add_argument(
        "--risk-aware",
        action="store_true",
        help="Use drawdown/Sharpe/Sortino-aware scoring instead of legacy strategy_score.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output CSV path. Defaults based on scoring mode.",
    )

    return parser.parse_args()


def read_rows(path):
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("")
        return

    fieldnames = list(rows[0].keys())

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_float(value, default=0.0):
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except Exception:
        return default


def money(value):
    return f"${safe_float(value):,.2f}"


def pct(value):
    return f"{safe_float(value) * 100:.2f}%"


def main():
    args = parse_args()

    summary = Path(args.summary)
    if not summary.exists():
        raise FileNotFoundError(f"Summary CSV not found: {summary}")

    if args.risk_aware:
        rows = read_rows(summary)
        scorer = RiskAwareStrategyScorer(
            profile=args.profile,
            min_trades=args.min_trades,
        )
        ranked = scorer.score_rows(rows)
        score_key = "risk_score"
        output = Path(
            args.output
            or "reports/backtest_experiments/risk_scored_summary.csv"
        )
        title = "Risk-Aware Strategy Scoring"
    else:
        scorer = StrategyScorer.from_profile(
            args.profile,
            min_trades=args.min_trades,
        )
        ranked = scorer.rank_file(str(summary))
        score_key = "strategy_score"
        output = Path(
            args.output
            or "reports/backtest_experiments/scored_summary.csv"
        )
        title = "Strategy Scoring"

    write_rows(output, ranked)

    print()
    print(f"========== {title} ==========")
    print(f"Summary File : {summary}")
    print(f"Runs         : {len(ranked)}")
    print(f"Min Trades   : {args.min_trades}")
    print(f"Profile      : {args.profile}")
    print(f"Risk Aware   : {args.risk_aware}")
    print()

    for idx, row in enumerate(ranked[:args.top], start=1):
        score = safe_float(row.get(score_key, row.get("strategy_score", 0.0)))
        grade = row.get("risk_grade", "")
        grade_part = f" | Grade={grade:>2}" if args.risk_aware else ""

        print(
            f"{idx:>2}. "
            f"Score={score:7.2f}{grade_part} | "
            f"Run={row.get('run', row.get('window', '')):>3} | "
            f"Trades={safe_int(row.get('trades', 0)):>3} | "
            f"Return={pct(row.get('return_pct', 0.0)):>8} | "
            f"PF={safe_float(row.get('profit_factor', 0.0)):5.2f} | "
            f"Win={pct(row.get('win_rate', 0.0)):>8} | "
            f"Sharpe={safe_float(row.get('sharpe_ratio', 0.0)):5.2f} | "
            f"DD={pct(row.get('max_drawdown_pct', 0.0)):>8} | "
            f"Exp={money(row.get('expectancy', 0.0)):>12} | "
            f"PnL={money(row.get('net_pnl', 0.0)):>12}"
        )

    print()
    print(f"Scored CSV   : {output}")
    print("======================================")
    print()


if __name__ == "__main__":
    main()
