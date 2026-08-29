import argparse
import csv
from pathlib import Path


def parse_args():

    parser = argparse.ArgumentParser(
        description="Analyze walk-forward summary"
    )

    parser.add_argument(
        "--summary",
        default="reports/walkforward/summary.csv",
    )

    return parser.parse_args()


def main():

    args = parse_args()

    path = Path(args.summary)

    if not path.exists():
        raise FileNotFoundError(path)

    with open(path, "r") as f:
        rows = list(csv.DictReader(f))

    ranked = sorted(
        rows,
        key=lambda r: (
            float(r["profit_factor"]),
            float(r["return_pct"]),
        ),
        reverse=True,
    )

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
    print("========== Walk-Forward Analysis ==========")
    print(f"Summary File : {path}")
    print(f"Windows      : {len(rows)}")
    print(f"Total PnL    : ${total_pnl:,.2f}")
    print(f"Avg Return   : {avg_return:.2%}")
    print(f"Avg PF       : {avg_pf:.2f}")
    print()

    print("Ranked Windows")
    print("-------------------------------------------")

    for row in ranked:
        print(
            f"Window={int(row['window']):>2} | "
            f"Test={row['test_start']}->{row['test_end']} | "
            f"Trades={int(row['trades']):>3} | "
            f"Return={float(row['return_pct']):7.2%} | "
            f"PF={float(row['profit_factor']):5.2f} | "
            f"PnL=${float(row['net_pnl']):,.2f}"
        )

    print("===========================================")
    print()


if __name__ == "__main__":
    main()
