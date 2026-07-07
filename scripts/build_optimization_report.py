import csv
from pathlib import Path


def money(value):
    return f"${float(value):,.2f}"


def pct(value):
    return f"{float(value) * 100:.2f}%"


def load_rows(path):
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def build_table(rows, columns):
    if not rows:
        return "<p>No data available.</p>"

    html = "<table><thead><tr>"

    for label, key in columns:
        html += f"<th>{label}</th>"

    html += "</tr></thead><tbody>"

    for row in rows:
        html += "<tr>"

        for _, key in columns:
            html += f"<td>{row.get(key, '')}</td>"

        html += "</tr>"

    html += "</tbody></table>"

    return html


def format_rows(rows):
    formatted = []

    for r in rows:
        formatted.append({
            "strategy_score": f"{float(r['strategy_score']):.2f}",
            "run": r.get("run", ""),
            "trades": r.get("trades", ""),
            "return_pct": pct(r.get("return_pct", 0.0)),
            "profit_factor": f"{float(r.get('profit_factor', 0.0)):.2f}",
            "win_rate": pct(r.get("win_rate", 0.0)),
            "expectancy": money(r.get("expectancy", 0.0)),
            "net_pnl": money(r.get("net_pnl", 0.0)),
            "option_premium_pct": pct(r.get("option_premium_pct", 0.0)),
            "take_profit": pct(r.get("take_profit", 0.0)),
            "stop_loss": pct(r.get("stop_loss", 0.0)),
            "max_hold": r.get("max_hold", ""),
            "min_delta": r.get("min_delta", ""),
            "max_delta": r.get("max_delta", ""),
            "min_vega": r.get("min_vega", ""),
            "max_vega": r.get("max_vega", ""),
            "max_theta": r.get("max_theta", ""),
            "run_dir": r.get("run_dir", ""),
        })

    return formatted


def main():

    scored_file = Path("reports/backtest_experiments/scored_summary.csv")

    if not scored_file.exists():
        raise FileNotFoundError(
            "Run score-strategies first to create scored_summary.csv"
        )

    rows = load_rows(scored_file)

    ranked = sorted(
        rows,
        key=lambda r: float(r["strategy_score"]),
        reverse=True,
    )

    display_rows = format_rows(ranked)

    top_rows = display_rows[:10]

    best = display_rows[0] if display_rows else {}

    columns = [
        ("Score", "strategy_score"),
        ("Run", "run"),
        ("Trades", "trades"),
        ("Return", "return_pct"),
        ("PF", "profit_factor"),
        ("Win Rate", "win_rate"),
        ("Expectancy", "expectancy"),
        ("Net PnL", "net_pnl"),
        ("Premium", "option_premium_pct"),
        ("TP", "take_profit"),
        ("SL", "stop_loss"),
        ("Hold", "max_hold"),
        ("Min Delta", "min_delta"),
        ("Max Delta", "max_delta"),
        ("Min Vega", "min_vega"),
        ("Max Vega", "max_vega"),
        ("Max Theta", "max_theta"),
        ("Run Dir", "run_dir"),
    ]

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Trading AI Optimization Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 30px;
            background: #f7f7f7;
            color: #222;
        }}
        h1, h2 {{
            color: #111;
        }}
        .card {{
            background: white;
            padding: 20px;
            margin-bottom: 25px;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.12);
            overflow-x: auto;
        }}
        .metric {{
            display: inline-block;
            margin-right: 30px;
            margin-bottom: 15px;
            font-size: 18px;
        }}
        .metric strong {{
            display: block;
            font-size: 13px;
            color: #666;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
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

<h1>Trading AI Optimization Report</h1>

<div class="card">
    <h2>Best Strategy</h2>
    <div class="metric"><strong>Score</strong>{best.get("strategy_score", "")}</div>
    <div class="metric"><strong>Run</strong>{best.get("run", "")}</div>
    <div class="metric"><strong>Trades</strong>{best.get("trades", "")}</div>
    <div class="metric"><strong>Return</strong>{best.get("return_pct", "")}</div>
    <div class="metric"><strong>Profit Factor</strong>{best.get("profit_factor", "")}</div>
    <div class="metric"><strong>Net PnL</strong>{best.get("net_pnl", "")}</div>
</div>

<div class="card">
    <h2>Top Strategies</h2>
    {build_table(top_rows, columns)}
</div>

<div class="card">
    <h2>All Scored Strategies</h2>
    {build_table(display_rows, columns)}
</div>

</body>
</html>
"""

    output = Path("reports/backtest_experiments/optimization_report.html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html)

    print(f"Optimization report created: {output}")


if __name__ == "__main__":
    main()
