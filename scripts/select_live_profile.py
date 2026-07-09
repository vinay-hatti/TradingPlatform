import csv
import json
from pathlib import Path


REPORT_DIR = Path("reports/walkforward")


def load_rows(path):
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def safe_float(value):
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def safe_int(value):
    try:
        if value in ("", None):
            return 0
        return int(float(value))
    except Exception:
        return 0


def avg(rows, key):
    if not rows:
        return 0.0
    return sum(safe_float(r.get(key, 0.0)) for r in rows) / len(rows)


def summarize(path):
    rows = load_rows(path)

    if not rows:
        return None

    total_pnl = sum(safe_float(r.get("net_pnl", 0.0)) for r in rows)
    avg_return = avg(rows, "return_pct")
    avg_pf = avg(rows, "profit_factor")
    total_trades = sum(safe_int(r.get("trades", 0)) for r in rows)
    winning_windows = sum(safe_float(r.get("net_pnl", 0.0)) > 0 for r in rows)

    avg_sharpe = avg(rows, "sharpe_ratio")
    avg_sortino = avg(rows, "sortino_ratio")
    avg_drawdown = avg(rows, "max_drawdown_pct")

    avg_risk_score = avg(rows, "risk_score")
    avg_train_sharpe = avg(rows, "train_sharpe")
    avg_train_sortino = avg(rows, "train_sortino")
    avg_train_drawdown = avg(rows, "train_max_drawdown_pct")
    avg_train_return = avg(rows, "train_return_pct")
    avg_train_pf = avg(rows, "train_profit_factor")

    consistency = winning_windows / len(rows)

    drawdown_score = max(
        0.0,
        100.0 - abs(avg_drawdown) * 100.0,
    )

    train_drawdown_score = max(
        0.0,
        100.0 - abs(avg_train_drawdown) * 100.0,
    )

    score = (
        min(avg_pf / 3.0, 1.0) * 15.0
        + min(avg_return / 0.20, 1.0) * 15.0
        + consistency * 15.0
        + min(total_trades / 50.0, 1.0) * 10.0
        + min(max(avg_sharpe, 0.0) / 2.0, 1.0) * 10.0
        + drawdown_score * 0.10
        + min(avg_risk_score / 100.0, 1.0) * 20.0
        + min(max(avg_train_sharpe, 0.0) / 2.0, 1.0) * 5.0
        + train_drawdown_score * 0.10
    )

    # Guardrails: high out-of-sample or selected-training drawdown is heavily penalized.
    if avg_drawdown < -0.50:
        score *= 0.70

    if avg_train_drawdown < -0.50:
        score *= 0.70

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
        "avg_risk_score": avg_risk_score,
        "avg_train_sharpe": avg_train_sharpe,
        "avg_train_sortino": avg_train_sortino,
        "avg_train_drawdown": avg_train_drawdown,
        "avg_train_return": avg_train_return,
        "avg_train_pf": avg_train_pf,
    }


def main():
    summaries = []

    for path in sorted(REPORT_DIR.glob("*.csv")):
        if path.name == "summary.csv":
            continue

        summary = summarize(path)
        if summary:
            summaries.append(summary)

    if not summaries:
        raise FileNotFoundError(
            f"No walk-forward profile CSVs found in {REPORT_DIR}."
        )

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
            f"RiskScore={row['avg_risk_score']:6.2f} | "
            f"PnL=${row['total_pnl']:>10,.2f} | "
            f"AvgReturn={row['avg_return']:>7.2%} | "
            f"AvgPF={row['avg_pf']:>5.2f} | "
            f"Consistency={row['consistency']:>6.2%} | "
            f"Trades={row['total_trades']} | "
            f"Sharpe={row['avg_sharpe']:>5.2f} | "
            f"DD={row['avg_drawdown']:>7.2%} | "
            f"TrainSharpe={row['avg_train_sharpe']:>5.2f} | "
            f"TrainDD={row['avg_train_drawdown']:>7.2%}"
        )

    print()
    print("Recommended Live Profile")
    print("-----------------------------------------------")
    print(f"Profile      : {best['profile']}")
    print(f"Score        : {best['score']:.2f}")
    print(f"Risk Score   : {best['avg_risk_score']:.2f}")
    print(f"Total PnL    : ${best['total_pnl']:,.2f}")
    print(f"Avg Return   : {best['avg_return']:.2%}")
    print(f"Avg PF       : {best['avg_pf']:.2f}")
    print(f"Consistency  : {best['consistency']:.2%}")
    print(f"Avg Sharpe   : {best['avg_sharpe']:.2f}")
    print(f"Avg Drawdown : {best['avg_drawdown']:.2%}")
    print(f"Train Sharpe : {best['avg_train_sharpe']:.2f}")
    print(f"Train DD     : {best['avg_train_drawdown']:.2%}")
    print(f"Saved JSON   : {output}")
    print("================================================")
    print()


if __name__ == "__main__":
    main()
