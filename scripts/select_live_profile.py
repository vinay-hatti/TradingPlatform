import csv
import json
from pathlib import Path


REPORT_DIR = Path("reports/walkforward")


def load_rows(path):
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def summarize(path):
    rows = load_rows(path)

    total_pnl = sum(safe_float(r["net_pnl"]) for r in rows)
    avg_return = sum(safe_float(r["return_pct"]) for r in rows) / len(rows)
    avg_pf = sum(safe_float(r["profit_factor"]) for r in rows) / len(rows)
    total_trades = sum(int(float(r["trades"])) for r in rows)
    winning_windows = sum(safe_float(r["net_pnl"]) > 0 for r in rows)
    avg_sharpe = sum(safe_float(r.get("sharpe_ratio", 0.0)) for r in rows) / len(rows)
    avg_sortino = sum(safe_float(r.get("sortino_ratio", 0.0)) for r in rows) / len(rows)
    avg_drawdown = sum(safe_float(r.get("max_drawdown_pct", 0.0)) for r in rows) / len(rows)

    consistency = winning_windows / len(rows)

    score = (
        min(avg_pf / 3.0, 1.0) * 40.0
        + min(avg_return / 0.20, 1.0) * 30.0
        + consistency * 20.0
        + min(total_trades / 50.0, 1.0) * 10.0
    )

    return {
        "profile": path.stem,
        "windows": len(rows),
        "winning_windows": winning_windows,
        "total_trades": total_trades,
        "total_pnl": total_pnl,
        "avg_return": avg_return,
        "avg_pf": avg_pf,
        "consistency": consistency,
        "score": score,
        "avg_sharpe": avg_sharpe,
        "avg_sortino": avg_sortino,
        "avg_drawdown": avg_drawdown,
    }


def main():
    summaries = []

    for path in sorted(REPORT_DIR.glob("*.csv")):
        if path.name == "summary.csv":
            continue

        summaries.append(summarize(path))

    summaries = sorted(
        summaries,
        key=lambda r: r["score"],
        reverse=True,
    )

    best = summaries[0]

    output = REPORT_DIR / "live_profile.json"

    with open(output, "w") as f:
        json.dump(best, f, indent=2)

    print()
    print("========== Automatic Live Profile Selection ==========")
    print()

    for idx, row in enumerate(summaries, start=1):
        print(
            f"{idx}. {row['profile']:32} "
            f"Score={row['score']:6.2f} | "
            f"PnL=${row['total_pnl']:>10,.2f} | "
            f"AvgReturn={row['avg_return']:>7.2%} | "
            f"AvgPF={row['avg_pf']:>5.2f} | "
            f"Consistency={row['consistency']:>6.2%} | "
            f"Trades={row['total_trades']}"
            f"Sharpe={row['avg_sharpe']:>5.2f} | "
            f"DD={row['avg_drawdown']:>7.2%} | "
        )

    print()
    print("Recommended Live Profile")
    print("-----------------------------------------------")
    print(f"Profile      : {best['profile']}")
    print(f"Score        : {best['score']:.2f}")
    print(f"Total PnL    : ${best['total_pnl']:,.2f}")
    print(f"Avg Return   : {best['avg_return']:.2%}")
    print(f"Avg PF       : {best['avg_pf']:.2f}")
    print(f"Consistency  : {best['consistency']:.2%}")
    print(f"Avg Sharpe  : {best['avg_sharpe']:.2f}")
    print(f"Avg Drawdown: {best['avg_drawdown']:.2%}")
    print(f"Saved JSON   : {output}")
    print("================================================")
    print()


if __name__ == "__main__":
    main()
