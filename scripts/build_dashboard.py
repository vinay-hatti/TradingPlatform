import csv
from pathlib import Path
from datetime import datetime


def latest_file(pattern):
    files = sorted(Path("reports").glob(pattern), reverse=True)
    return files[0] if files else None


def load_csv(path):
    if path is None:
        return []

    with open(path, "r") as f:
        return list(csv.DictReader(f))


def money(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


def pct(value):
    try:
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return "0.00%"


def build_table(rows, columns):
    if not rows:
        return "<p>No data available.</p>"

    html = "<table><thead><tr>"

    for col in columns:
        html += f"<th>{col}</th>"

    html += "</tr></thead><tbody>"

    for row in rows:
        html += "<tr>"
        for col in columns:
            html += f"<td>{row.get(col, '')}</td>"
        html += "</tr>"

    html += "</tbody></table>"

    return html


def main():

    scanner_file = latest_file("scanner_results_*.csv")
    optimized_file = latest_file("optimized_portfolio_*.csv")

    scanner_rows = load_csv(scanner_file)
    optimized_rows = load_csv(optimized_file)

    total_allocated = sum(
        float(r.get("final_allocation", 0.0))
        for r in optimized_rows
        if r.get("status") == "ACCEPTED"
    )

    capital = 100000.0
    cash = capital - total_allocated
    heat = total_allocated / capital if capital else 0.0

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Trading AI Dashboard</title>
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
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
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
        .metric {{
            display: inline-block;
            margin-right: 30px;
            font-size: 18px;
        }}
        .metric strong {{
            display: block;
            font-size: 13px;
            color: #666;
        }}
    </style>
</head>
<body>

<h1>Trading AI Dashboard</h1>
<p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

<div class="card">
    <h2>Portfolio Summary</h2>
    <div class="metric"><strong>Capital</strong>{money(capital)}</div>
    <div class="metric"><strong>Allocated</strong>{money(total_allocated)}</div>
    <div class="metric"><strong>Cash</strong>{money(cash)}</div>
    <div class="metric"><strong>Portfolio Heat</strong>{pct(heat)}</div>
</div>

<div class="card">
    <h2>Optimized Portfolio</h2>
    <p>Source: {optimized_file}</p>
    {build_table(
        optimized_rows,
        [
            "symbol",
            "signal",
            "strategy",
            "confidence",
            "rank_score",
            "win_probability",
            "reward_risk",
            "kelly_fraction",
            "option_price_estimate",
            "contract_cost",
            "final_allocation",
            "recommended_contracts",
            "status",
            "reason",
        ],
    )}
</div>

<div class="card">
    <h2>Scanner Candidates</h2>
    <p>Source: {scanner_file}</p>
    {build_table(
        scanner_rows,
        [
            "symbol",
            "signal",
            "strategy",
            "rank_score",
            "confidence",
            "affordability_status",
            "recommended_position_value",
            "option_price_estimate",
            "estimated_contract_cost",
            "recommended_contracts",
            "win_probability",
            "reward_risk",
            "kelly_fraction",
            "regime",
            "strike",
            "expiry",
            "delta",
            "iv",
        ],
    )}
</div>

</body>
</html>
"""

    Path("reports").mkdir(exist_ok=True)

    output = Path("reports/dashboard.html")
    output.write_text(html)

    print(f"Dashboard created: {output}")


if __name__ == "__main__":
    main()
