import argparse
import csv
from collections import defaultdict
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze backtest experiment summary"
    )

    parser.add_argument(
        "--summary",
        default="reports/backtest_experiments/summary.csv",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=10,
    )

    return parser.parse_args()


def load_rows(path):
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def avg(values):
    values = [float(v) for v in values]
    return sum(values) / len(values) if values else 0.0


def print_top(rows, top):

    ranked = sorted(
        rows,
        key=lambda r: (
            float(r["profit_factor"]),
            float(r["return_pct"]),
        ),
        reverse=True,
    )

    print()
    print("========== Top Experiments ==========")

    for idx, row in enumerate(ranked[:top], start=1):
        print(
            f"{idx:>2}. "
            f"Run={row['run']:>3} | "
            f"Premium={float(row['option_premium_pct']):6.2%} | "
            f"TP={float(row['take_profit']):6.2%} | "
            f"SL={float(row['stop_loss']):6.2%} | "
            f"Hold={int(row['max_hold']):>2} | "
            f"Trades={int(row['trades']):>3} | "
            f"Return={float(row['return_pct']):7.2%} | "
            f"PF={float(row['profit_factor']):5.2f} | "
            f"PnL=${float(row['net_pnl']):,.2f}"
        )

    print("=====================================")


def print_grouped(rows, field):

    grouped = defaultdict(list)

    for row in rows:
        grouped[row[field]].append(row)

    print()
    print(f"========== Average by {field} ==========")

    for value, group_rows in sorted(
        grouped.items(),
        key=lambda item: float(item[0])
        if str(item[0]).replace(".", "", 1).replace("-", "", 1).isdigit()
        else str(item[0]),
    ):
        print(
            f"{field}={value:>8} | "
            f"Runs={len(group_rows):>3} | "
            f"AvgReturn={avg([r['return_pct'] for r in group_rows]):7.2%} | "
            f"AvgPF={avg([r['profit_factor'] for r in group_rows]):5.2f} | "
            f"AvgPnL=${avg([r['net_pnl'] for r in group_rows]):,.2f}"
        )

    print("========================================")


def main():

    args = parse_args()

    path = Path(args.summary)

    if not path.exists():
        raise FileNotFoundError(
            f"Summary file not found: {path}"
        )

    rows = load_rows(path)

    print()
    print("========== Experiment Analysis ==========")
    print(f"Summary File : {path}")
    print(f"Runs         : {len(rows)}")
    print("=========================================")

    print_top(rows, args.top)

    for field in [
        "option_premium_pct",
        "take_profit",
        "stop_loss",
        "max_hold",
    ]:
        if field in rows[0]:
            print_grouped(rows, field)


if __name__ == "__main__":
    main()
