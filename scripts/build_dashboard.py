import csv
import json
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


def load_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, "r") as f:
        return json.load(f)


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


def main():

    scanner_file = latest_file("scanner_results_*.csv")
    optimized_file = latest_file("optimized_portfolio_*.csv")

    scanner_rows = load_csv(scanner_file)
    optimized_rows = load_csv(optimized_file)

    accepted_optimized = [
        r for r in optimized_rows
        if r.get("status") == "ACCEPTED"
    ]

    latest_risk = accepted_optimized[-1] if accepted_optimized else {}

    paper_positions = load_json("data/paper/positions.json", [])
    paper_cash = load_json("data/paper/cash.json", {"cash": 100000.0})

    open_positions = [p for p in paper_positions if p.get("status") == "OPEN"]
    closed_positions = [p for p in paper_positions if p.get("status") == "CLOSED"]

    paper_cash_value = float(paper_cash.get("cash", 100000.0))

    paper_open_value = sum(
        float(p.get("current_price", 0.0))
        * int(p.get("quantity", 0))
        * 100.0
        for p in open_positions
    )

    paper_unrealized = sum(
        float(p.get("unrealized_pnl", 0.0))
        for p in open_positions
    )

    paper_realized = sum(
        float(p.get("realized_pnl", 0.0))
        for p in closed_positions
    )

    paper_net_liq = paper_cash_value + paper_open_value

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
            overflow-x: auto;
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
    </style>
</head>
<body>

<h1>Trading AI Dashboard</h1>
<p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

<div class="card">
    <h2>Optimized Portfolio Summary</h2>
    <div class="metric"><strong>Capital</strong>{money(capital)}</div>
    <div class="metric"><strong>Allocated</strong>{money(total_allocated)}</div>
    <div class="metric"><strong>Cash</strong>{money(cash)}</div>
    <div class="metric"><strong>Portfolio Heat</strong>{pct(heat)}</div>
</div>

<div class="card">
    <h2>Risk Summary</h2>
    <div class="metric"><strong>Portfolio Heat</strong>{pct(latest_risk.get("risk_portfolio_heat", 0.0))}</div>
    <div class="metric"><strong>Cash Reserve</strong>{pct(latest_risk.get("risk_cash_reserve", 0.0))}</div>
    <div class="metric"><strong>Symbol Exposure</strong>{pct(latest_risk.get("risk_symbol_exposure", 0.0))}</div>
    <div class="metric"><strong>Sector Exposure</strong>{pct(latest_risk.get("risk_sector_exposure", 0.0))}</div>
    <div class="metric"><strong>Strategy Exposure</strong>{pct(latest_risk.get("risk_strategy_exposure", 0.0))}</div>
    <div class="metric"><strong>Net Delta</strong>{latest_risk.get("risk_net_delta", "0.00")}</div>
</div>

<div class="card">
    <h2>Paper Trading Status</h2>
    <div class="metric"><strong>Cash</strong>{money(paper_cash_value)}</div>
    <div class="metric"><strong>Open Value</strong>{money(paper_open_value)}</div>
    <div class="metric"><strong>Net Liquidation</strong>{money(paper_net_liq)}</div>
    <div class="metric"><strong>Unrealized PnL</strong>{money(paper_unrealized)}</div>
    <div class="metric"><strong>Realized PnL</strong>{money(paper_realized)}</div>
    <div class="metric"><strong>Open Positions</strong>{len(open_positions)}</div>
    <div class="metric"><strong>Closed Positions</strong>{len(closed_positions)}</div>
</div>

<div class="card">
    <h2>Open Paper Positions</h2>
    {build_table(
        open_positions,
        [
            ("Symbol", "symbol"),
            ("Side", "signal"),
            ("Strategy", "strategy"),
            ("Strike", "strike"),
            ("Expiry", "expiry"),
            ("Qty", "quantity"),
            ("Entry", "entry_price"),
            ("Current", "current_price"),
            ("Unrealized PnL", "unrealized_pnl"),
            ("IV", "implied_volatility"),
            ("Opened", "opened_at"),
            ("Status", "status"),
        ],
    )}
</div>

<div class="card">
    <h2>Closed Paper Positions</h2>
    {build_table(
        closed_positions,
        [
            ("Symbol", "symbol"),
            ("Side", "signal"),
            ("Strategy", "strategy"),
            ("Qty", "quantity"),
            ("Entry", "entry_price"),
            ("Exit", "exit_price"),
            ("Realized PnL", "realized_pnl"),
            ("Exit Reason", "exit_reason"),
            ("Opened", "opened_at"),
            ("Closed", "closed_at"),
            ("Status", "status"),
        ],
    )}
</div>

<div class="card">
    <h2>Optimized Portfolio</h2>
    <p>Source: {optimized_file}</p>
    {build_table(
        optimized_rows,
        [
            ("Symbol", "symbol"),
            ("Side", "signal"),
            ("Strategy", "strategy"),
            ("Confidence", "confidence"),
            ("Status", "status"),
            ("Reason", "reason"),

            ("Rank", "rank_score"),
            ("Option Score", "option_score"),
            ("POP", "probability_of_profit"),
            ("Win Prob", "win_probability"),
            ("Reward/Risk", "reward_risk"),
            ("Kelly", "kelly_fraction"),

            ("Strike", "strike"),
            ("Expiry", "expiry"),
            ("IV", "iv"),
            ("Option Price", "option_price_estimate"),
            ("Contract Cost", "contract_cost"),
            ("Allocation", "final_allocation"),
            ("Qty", "recommended_contracts"),

            ("Risk Heat", "risk_portfolio_heat"),
            ("Cash Reserve", "risk_cash_reserve"),
            ("Symbol Exposure", "risk_symbol_exposure"),
            ("Sector Exposure", "risk_sector_exposure"),
            ("Strategy Exposure", "risk_strategy_exposure"),
            ("Net Delta", "risk_net_delta"),

            ("Liquidity", "liquidity_score"),
            ("Delta Score", "delta_score"),
            ("IV Score", "iv_score"),
        ],
    )}
</div>

<div class="card">
    <h2>Scanner Candidates</h2>
    <p>Source: {scanner_file}</p>
    {build_table(
        scanner_rows,
        [
            ("Symbol", "symbol"),
            ("Side", "signal"),
            ("Strategy", "strategy"),
            ("Confidence", "confidence"),
            ("Affordability", "affordability_status"),

            ("Rank", "rank_score"),
            ("Option Score", "option_score"),
            ("POP", "probability_of_profit"),
            ("Win Prob", "win_probability"),
            ("Reward/Risk", "reward_risk"),
            ("Kelly", "kelly_fraction"),

            ("Regime", "regime"),
            ("Strike", "strike"),
            ("Expiry", "expiry"),
            ("DTE", "days_to_expiry"),
            ("Delta", "delta"),
            ("IV", "iv"),
            ("Liquidity", "liquidity_score"),

            ("Position Value", "recommended_position_value"),
            ("Option Price", "option_price_estimate"),
            ("Contract Cost", "estimated_contract_cost"),
            ("Qty", "recommended_contracts"),
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
