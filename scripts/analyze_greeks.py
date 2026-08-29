import argparse
import csv
from pathlib import Path


def latest_trades_file():
    files = sorted(
        Path("reports/backtests").glob("*/trades.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    return files[0] if files else None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze Greek distribution and performance"
    )

    parser.add_argument(
        "--trades",
        default=None,
        help="Path to trades.csv. Defaults to latest backtest trades.csv.",
    )

    return parser.parse_args()


def load_rows(path):
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def bucket_delta(delta):
    delta = abs(float(delta))

    if delta < 0.30:
        return "0.00-0.30"
    if delta < 0.40:
        return "0.30-0.40"
    if delta < 0.45:
        return "0.40-0.45"
    if delta < 0.50:
        return "0.45-0.50"
    if delta < 0.60:
        return "0.50-0.60"
    if delta < 0.75:
        return "0.60-0.75"

    return "0.75+"


def bucket_theta(theta):
    theta = abs(float(theta))

    if theta < 0.03:
        return "0.00-0.03"
    if theta < 0.05:
        return "0.03-0.05"
    if theta < 0.08:
        return "0.05-0.08"
    if theta < 0.12:
        return "0.08-0.12"

    return "0.12+"


def bucket_vega(vega):
    vega = float(vega)

    if vega < 0.20:
        return "0.00-0.20"
    if vega < 0.30:
        return "0.20-0.30"
    if vega < 0.40:
        return "0.30-0.40"
    if vega < 0.60:
        return "0.40-0.60"

    return "0.60+"


def metrics(rows):
    pnls = [float(r["net_pnl"] or r["pnl"]) for r in rows]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    return {
        "trades": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(rows) if rows else 0.0,
        "net_pnl": sum(pnls),
        "profit_factor": (
            gross_profit / gross_loss
            if gross_loss > 0
            else float("inf")
        ),
        "expectancy": sum(pnls) / len(rows) if rows else 0.0,
    }


def grouped_report(rows, name, bucket_fn, source_field):
    grouped = {}

    for row in rows:
        bucket = bucket_fn(row[source_field])
        grouped.setdefault(bucket, []).append(row)

    print()
    print(f"========== Performance by {name} ==========")

    for bucket, bucket_rows in sorted(grouped.items()):
        m = metrics(bucket_rows)

        print(
            f"{bucket:12} | "
            f"Trades={m['trades']:>3} | "
            f"Win={m['win_rate']:>7.2%} | "
            f"PF={m['profit_factor']:>5.2f} | "
            f"PnL=${m['net_pnl']:>10,.2f} | "
            f"Exp=${m['expectancy']:>8,.2f}"
        )

    print("===========================================")


def average(rows, field):
    values = [float(r[field]) for r in rows if r.get(field) not in ("", None)]

    return sum(values) / len(values) if values else 0.0


def main():
    args = parse_args()

    path = Path(args.trades) if args.trades else latest_trades_file()

    if path is None or not path.exists():
        raise FileNotFoundError("No trades.csv found.")

    rows = load_rows(path)

    print()
    print("========== Greeks Analyzer ==========")
    print(f"Trades File : {path}")
    print(f"Trades      : {len(rows)}")
    print()
    print("Averages")
    print("-------------------------------------")
    print(f"Delta       : {average(rows, 'entry_delta'):.4f}")
    print(f"Abs Delta   : {sum(abs(float(r['entry_delta'])) for r in rows) / len(rows):.4f}")
    print(f"Gamma       : {average(rows, 'entry_gamma'):.5f}")
    print(f"Theta       : {average(rows, 'entry_theta'):.4f}")
    print(f"Vega        : {average(rows, 'entry_vega'):.4f}")
    print(f"Rho         : {average(rows, 'entry_rho'):.4f}")
    print(f"Volatility  : {average(rows, 'entry_volatility'):.2%}")
    print("=====================================")

    grouped_report(
        rows,
        "Delta Bucket",
        bucket_delta,
        "entry_delta",
    )

    grouped_report(
        rows,
        "Theta Bucket",
        bucket_theta,
        "entry_theta",
    )

    grouped_report(
        rows,
        "Vega Bucket",
        bucket_vega,
        "entry_vega",
    )


if __name__ == "__main__":
    main()
