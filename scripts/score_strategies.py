import argparse
import csv
from pathlib import Path

from trading_ai.optimization.strategy_scorer import StrategyScorer


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

    return parser.parse_args()


def main():

    args = parse_args()

    scorer = StrategyScorer.from_profile(
        args.profile,
        min_trades=args.min_trades,
    )

    ranked = scorer.rank_file(args.summary)

    output = Path("reports/backtest_experiments/scored_summary.csv")
    output.parent.mkdir(parents=True, exist_ok=True)

    if ranked:
        fieldnames = list(ranked[0].keys())

        with open(output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(ranked)

    print()
    print("========== Strategy Scoring ==========")
    print(f"Summary File : {args.summary}")
    print(f"Runs         : {len(ranked)}")
    print(f"Min Trades   : {args.min_trades}")
    print(f"Profile      : {args.profile}")
    print()

    for idx, row in enumerate(ranked[:args.top], start=1):
        print(
            f"{idx:>2}. "
            f"Score={float(row['strategy_score']):7.2f} | "
            f"Run={row.get('run', ''):>3} | "
            f"Trades={int(float(row.get('trades', 0))):>3} | "
            f"Return={float(row.get('return_pct', 0.0)):7.2%} | "
            f"PF={float(row.get('profit_factor', 0.0)):5.2f} | "
            f"Win={float(row.get('win_rate', 0.0)):6.2%} | "
            f"Exp=${float(row.get('expectancy', 0.0)):,.2f} | "
            f"PnL=${float(row.get('net_pnl', 0.0)):,.2f}"
        )

    print()
    print(f"Scored CSV   : {output}")
    print("======================================")
    print()


if __name__ == "__main__":
    main()
