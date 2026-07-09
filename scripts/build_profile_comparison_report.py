import csv
from pathlib import Path


REPORT_DIR = Path("reports/walkforward")
OUTPUT = REPORT_DIR / "profile_comparison.html"


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


def money(x):
    return f"${safe_float(x):,.2f}"


def pct(x):
    return f"{safe_float(x) * 100:.2f}%"


def load_rows(csv_file):
    with open(csv_file, "r") as f:
        return list(csv.DictReader(f))


def avg(rows, key):
    if not rows:
        return 0.0
    return sum(safe_float(r.get(key, 0.0)) for r in rows) / len(rows)


def load_summary(csv_file):
    rows = load_rows(csv_file)

    if not rows:
        return None

    total_pnl = sum(safe_float(r.get("net_pnl", 0.0)) for r in rows)
    total_trades = sum(safe_int(r.get("trades", 0)) for r in rows)
    winning_windows = sum(safe_float(r.get("net_pnl", 0.0)) > 0 for r in rows)

    avg_return = avg(rows, "return_pct")
    avg_pf = avg(rows, "profit_factor")
    avg_sharpe = avg(rows, "sharpe_ratio")
    avg_sortino = avg(rows, "sortino_ratio")
    avg_drawdown = avg(rows, "max_drawdown_pct")

    avg_risk_score = avg(rows, "risk_score")
    avg_train_sharpe = avg(rows, "train_sharpe")
    avg_train_sortino = avg(rows, "train_sortino")
    avg_train_drawdown = avg(rows, "train_max_drawdown_pct")
    avg_train_return = avg(rows, "train_return_pct")
    avg_train_pf = avg(rows, "train_profit_factor")

    consistency = winning_windows / len(rows) if rows else 0.0

    # Comparison score rewards out-of-sample PnL/return/PF and adds risk-aware training diagnostics.
    drawdown_score = max(0.0, 100.0 - abs(avg_drawdown) * 100.0)
    train_drawdown_score = max(0.0, 100.0 - abs(avg_train_drawdown) * 100.0)

    comparison_score = (
        min(avg_pf / 3.0, 1.0) * 20.0
        + min(avg_return / 0.20, 1.0) * 20.0
        + consistency * 15.0
        + min(total_trades / 50.0, 1.0) * 10.0
        + min(max(avg_sharpe, 0.0) / 2.0, 1.0) * 10.0
        + drawdown_score * 0.10
        + min(avg_risk_score / 100.0, 1.0) * 15.0
        + min(max(avg_train_sharpe, 0.0) / 2.0, 1.0) * 5.0
        + train_drawdown_score * 0.05
    )

    return {
        "profile": csv_file.stem,
        "windows": len(rows),
        "winning_windows": winning_windows,
        "consistency": consistency,
        "total_trades": total_trades,
        "total_pnl": total_pnl,
        "avg_return": avg_return,
        "avg_pf": avg_pf,
        "avg_sharpe": avg_sharpe,
        "avg_sortino": avg_sortino,
        "avg_drawdown": avg_drawdown,
        "avg_risk_score": avg_risk_score,
        "avg_train_sharpe": avg_train_sharpe,
        "avg_train_sortino": avg_train_sortino,
        "avg_train_drawdown": avg_train_drawdown,
        "avg_train_return": avg_train_return,
        "avg_train_pf": avg_train_pf,
        "comparison_score": comparison_score,
    }


def collect_profiles():
    profiles = []

    for csv_file in sorted(REPORT_DIR.glob("*.csv")):
        if csv_file.name == "summary.csv":
            continue

        summary = load_summary(csv_file)

        if summary:
            profiles.append(summary)

    profiles.sort(
        key=lambda x: (
            x["comparison_score"],
            x["total_pnl"],
            x["avg_pf"],
        ),
        reverse=True,
    )

    return profiles


def build_html(profiles):
    html = """
<html>
<head>
<title>Walk-Forward Profile Comparison</title>
<style>
body{
font-family:Arial;
margin:30px;
background:#f5f5f5;
}
.card{
background:white;
padding:20px;
margin-bottom:20px;
border-radius:8px;
box-shadow:0 0 4px rgba(0,0,0,.15);
overflow-x:auto;
}
table{
border-collapse:collapse;
width:100%;
white-space:nowrap;
}
th,td{
padding:8px;
border-bottom:1px solid #ddd;
text-align:left;
font-size:14px;
}
th{
background:#eee;
}
.best{
background:#dff0d8;
font-weight:bold;
}
.negative{
color:#b71c1c;
font-weight:bold;
}
.positive{
color:#1b5e20;
font-weight:bold;
}
</style>
</head>
<body>
<h1>Walk-Forward Profile Comparison</h1>
<div class="card">
<table>
<tr>
<th>Rank</th>
<th>Profile</th>
<th>Score</th>
<th>Windows</th>
<th>Winning Windows</th>
<th>Consistency</th>
<th>Total Trades</th>
<th>Total PnL</th>
<th>Avg Return</th>
<th>Avg PF</th>
<th>Avg Sharpe</th>
<th>Avg Sortino</th>
<th>Avg Drawdown</th>
<th>Risk Score</th>
<th>Train Sharpe</th>
<th>Train Sortino</th>
<th>Train DD</th>
<th>Train Return</th>
<th>Train PF</th>
</tr>
"""

    for i, p in enumerate(profiles):
        css = "best" if i == 0 else ""
        dd_css = "negative" if p["avg_drawdown"] < 0 else "positive"
        train_dd_css = "negative" if p["avg_train_drawdown"] < 0 else "positive"

        html += f"""
<tr class="{css}">
<td>{i + 1}</td>
<td>{p['profile']}</td>
<td>{p['comparison_score']:.2f}</td>
<td>{p['windows']}</td>
<td>{p['winning_windows']}</td>
<td>{pct(p['consistency'])}</td>
<td>{p['total_trades']}</td>
<td>{money(p['total_pnl'])}</td>
<td>{pct(p['avg_return'])}</td>
<td>{p['avg_pf']:.2f}</td>
<td>{p['avg_sharpe']:.2f}</td>
<td>{p['avg_sortino']:.2f}</td>
<td class="{dd_css}">{pct(p['avg_drawdown'])}</td>
<td>{p['avg_risk_score']:.2f}</td>
<td>{p['avg_train_sharpe']:.2f}</td>
<td>{p['avg_train_sortino']:.2f}</td>
<td class="{train_dd_css}">{pct(p['avg_train_drawdown'])}</td>
<td>{pct(p['avg_train_return'])}</td>
<td>{p['avg_train_pf']:.2f}</td>
</tr>
"""

    html += """
</table>
</div>
</body>
</html>
"""

    return html


def main():
    profiles = collect_profiles()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_html(profiles))

    print()
    print("========== Walk-Forward Profile Comparison ==========")
    print()

    for i, p in enumerate(profiles):
        print(
            f"{i + 1:2}. "
            f"{p['profile']:32} "
            f"Score={p['comparison_score']:6.2f} "
            f"PnL={money(p['total_pnl']):>12} "
            f"Return={pct(p['avg_return']):>8} "
            f"PF={p['avg_pf']:.2f} "
            f"Sharpe={p['avg_sharpe']:.2f} "
            f"DD={pct(p['avg_drawdown']):>8} "
            f"RiskScore={p['avg_risk_score']:.2f} "
            f"TrainSharpe={p['avg_train_sharpe']:.2f} "
            f"TrainDD={pct(p['avg_train_drawdown']):>8}"
        )

    print()
    print(f"Report: {OUTPUT}")


if __name__ == "__main__":
    main()
