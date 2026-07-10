import csv
from pathlib import Path


def latest_trades():
    files = sorted(
        Path("reports/backtests").glob("*/trades.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    return files[0] if files else None


def main():
    path = latest_trades()

    if not path:
        raise FileNotFoundError("No trades.csv found.")

    rows = list(csv.DictReader(open(path)))

    grouped = {}

    for row in rows:
        source = row.get("pricing_source", "unknown")
        grouped.setdefault(source, []).append(row)

    print()
    print("========== Option Pricing Source Comparison ==========")
    print(f"Trades File : {path}")
    print("------------------------------------------------------")

    for source, source_rows in grouped.items():
        pnl = sum(float(r.get("net_pnl", r.get("pnl", 0.0))) for r in source_rows)
        trades = len(source_rows)
        avg_pnl = pnl / trades if trades else 0.0

        print(
            f"{source:24} | "
            f"Trades={trades:4} | "
            f"NetPnL=${pnl:,.2f} | "
            f"AvgPnL=${avg_pnl:,.2f}"
        )

    print("======================================================")
    print()


if __name__ == "__main__":
    main()
