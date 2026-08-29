import argparse
import csv
from pathlib import Path

from trading_ai.optimization.risk_aware_scorer import RiskAwareStrategyScorer


def read_rows(path):
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    if not rows:
        return

    fieldnames = list(rows[0].keys())

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def money(value):
    return f"${float(value):,.2f}"


def pct(value):
    return f"{float(value) * 100:.2f}%"


def main():
    parser = argparse.ArgumentParser(
        description="Risk-aware strategy scoring"
    )

    parser.add_argument(
        "--summary",
        default="reports/backtest_experiments/summary.csv",
    )
    parser.add_argument(
        "--output",
        default="reports/backtest_experiments/risk_scored_summary.csv",
    )
    parser.add_argument(
        "--profile",
        default="balanced",
        choices=["conservative", "balanced", "aggressive"],
    )
    parser.add_argument("--min-trades", type=int, default=10)
    parser.add_argument("--top", type=int, default=20)

    args = parser.parse_args()

    rows = read_rows(args.summary)

    scorer = RiskAwareStrategyScorer(
        profile=args.profile,
        min_trades=args.min_trades,
    )

    scored = scorer.score_rows(rows)

    write_rows(args.output, scored)

    print()
    print("========== Risk-Aware Strategy Scoring ==========")
    print(f"Summary File : {args.summary}")
    print(f"Profile      : {args.profile}")
    print(f"Min Trades   : {args.min_trades}")
    print(f"Rows         : {len(scored)}")
    print("-----------------------------------------------")

    for idx, row in enumerate(scored[:args.top], start=1):
        print(
            f"{idx:2}. "
            f"Score={float(row.get('risk_score', 0.0)):7.2f} | "
            f"Grade={row.get('risk_grade', ''):>2} | "
            f"Run={row.get('run', row.get('window', '')):>3} | "
            f"Trades={int(float(row.get('trades', 0))):3} | "
            f"Return={pct(row.get('return_pct', 0.0)):>8} | "
            f"PF={float(row.get('profit_factor', 0.0)):5.2f} | "
            f"Sharpe={float(row.get('sharpe_ratio', 0.0)):5.2f} | "
            f"DD={pct(row.get('max_drawdown_pct', 0.0)):>8} | "
            f"PnL={money(row.get('net_pnl', 0.0)):>12}"
        )

    print("-----------------------------------------------")
    print(f"Output CSV   : {args.output}")
    print("================================================")
    print()


if __name__ == "__main__":
    main()
