import csv
from pathlib import Path


def read_rows(path):
    if not Path(path).exists():
        return []

    with open(path, "r") as f:
        return list(csv.DictReader(f))


def safe_float(value, default=0.0):
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default


def money(value):
    return f"${safe_float(value):,.2f}"


def pct(value):
    return f"{safe_float(value) * 100:.2f}%"

def html_table(rows):
    if not rows:
        return "<p>No data available.</p>"

    cols = [
        "run",
        "risk_score",
        "risk_grade",
        "trades",
        "return_pct",
        "profit_factor",
        "sharpe_ratio",
        "sortino_ratio",
        "max_drawdown_pct",
        "net_pnl",
        "risk_reason",
    ]

    html = "<table><thead><tr>"

    for c in cols:
        html += f"<th>{c}</th>"

    html += "</tr></thead><tbody>"

    for r in rows:
        html += "<tr>"
        for c in cols:
            value = r.get(c, "")

            if c in ("return_pct", "max_drawdown_pct"):
                value = pct(value)
            elif c == "net_pnl":
                value = money(value)
            elif c in ("risk_score", "profit_factor", "sharpe_ratio", "sortino_ratio"):
                value = f"{safe_float(value):.2f}"

            html += f"<td>{value}</td>"

        html += "</tr>"

    html += "</tbody></table>"

    return html


def main():
    path = "reports/backtest_experiments/risk_scored_summary.csv"
    rows = read_rows(path)

    rows = sorted(
        rows,
        key=lambda r: float(r.get("risk_score", 0.0)),
        reverse=True,
    )

    top = rows[:25]

    html = f"""
<!DOCTYPE html>
<html>
<head>
<title>Risk-Aware Optimization Report</title>
<style>
body {{
    font-family: Arial, sans-serif;
    margin: 30px;
    background: #f7f7f7;
}}
.card {{
    background: white;
    padding: 20px;
    border-radius: 8px;
    margin-bottom: 25px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.12);
    overflow-x: auto;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    white-space: nowrap;
}}
th, td {{
    border-bottom: 1px solid #ddd;
    padding: 8px;
    text-align: left;
    font-size: 14px;
}}
th {{
    background: #eee;
}}
</style>
</head>
<body>
<h1>Risk-Aware Optimization Report</h1>

<div class="card">
<h2>Top Risk-Aware Strategies</h2>
{html_table(top)}
</div>

</body>
</html>
"""

    out = Path("reports/backtest_experiments/risk_optimization_report.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)

    print()
    print("========== Risk Optimization Report ==========")
    print(f"Input : {path}")
    print(f"HTML  : {out}")
    print("==============================================")
    print()


if __name__ == "__main__":
    main()
