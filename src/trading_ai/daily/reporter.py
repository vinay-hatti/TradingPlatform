import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path


class DailyRecommendationReporter:

    def __init__(
        self,
        base_dir="reports/daily",
    ):
        self.base_dir = Path(base_dir)

    def money(self, value):
        return f"${float(value):,.2f}"

    def pct(self, value):
        return f"{float(value) * 100:.2f}%"

    def run_dir(self, report_date=None):

        if report_date is None:
            report_date = date.today().isoformat()

        path = self.base_dir / str(report_date)
        path.mkdir(parents=True, exist_ok=True)

        return path

    def candidate_dict(self, candidate):

        return asdict(candidate)

    def export_json(self, candidates, path, metadata, portfolio_summary):

        payload = {
            "metadata": metadata,
            "portfolio": portfolio_summary,
            "candidates": [
                self.candidate_dict(c)
                for c in candidates
            ],
        }

        with open(path, "w") as f:
            json.dump(payload, f, indent=2)

        return path

    def export_csv(self, candidates, path):

        fieldnames = [
            "symbol",
            "sector",
            "signal",
            "strategy",
            "adjusted_score",
            "final_score",
            "portfolio_penalty",
            "portfolio_notes",
            "score",
            "call_score",
            "put_score",
            "market_regime",
            "close",
            "strike",
            "expiry",
            "option_price",
            "delta",
            "gamma",
            "theta",
            "vega",
            "rho",
            "volatility",
            "dte",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
            )

            writer.writeheader()

            for c in candidates:
                row = self.candidate_dict(c)
                row["portfolio_notes"] = " | ".join(
                    row.get("portfolio_notes", [])
                )

                writer.writerow({
                    key: row.get(key, "")
                    for key in fieldnames
                })

        return path

    def build_table(self, rows, columns):

        if not rows:
            return "<p>No recommendations.</p>"

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

    def formatted_rows(self, candidates):

        rows = []

        for c in candidates:
            rows.append({
                "symbol": c.symbol,
                "sector": c.sector,
                "signal": c.signal,
                "strategy": c.strategy,
                "adjusted_score": f"{c.adjusted_score:.2f}",
                "final_score": f"{c.final_score:.2f}",
                "portfolio_penalty": f"{c.portfolio_penalty:.2f}",
                "portfolio_notes": " | ".join(c.portfolio_notes),
                "signal_score": f"{c.score:.2f}",
                "call_score": f"{c.call_score:.2f}",
                "put_score": f"{c.put_score:.2f}",
                "regime": c.market_regime,
                "underlying": self.money(c.close),
                "strike": self.money(c.strike),
                "option_price": self.money(c.option_price),
                "expiry": c.expiry,
                "delta": f"{c.delta:.4f}",
                "gamma": f"{c.gamma:.5f}",
                "theta": f"{c.theta:.4f}",
                "vega": f"{c.vega:.4f}",
                "rho": f"{c.rho:.4f}",
                "volatility": self.pct(c.volatility),
                "dte": c.dte,
            })

        return rows

    def portfolio_rows(self, portfolio_summary):

        rows = []

        for symbol, count in portfolio_summary.get("by_symbol", {}).items():
            rows.append({
                "type": "Symbol",
                "name": symbol,
                "positions": count,
            })

        for sector, count in portfolio_summary.get("by_sector", {}).items():
            rows.append({
                "type": "Sector",
                "name": sector,
                "positions": count,
            })

        return rows

    def generate_html(
        self,
        candidates,
        path,
        metadata,
        portfolio_summary,
    ):
        rows = self.formatted_rows(candidates)

        portfolio_rows = self.portfolio_rows(portfolio_summary)

        top_calls = [
            r for r in rows
            if r["signal"] == "CALL"
        ]

        top_puts = [
            r for r in rows
            if r["signal"] == "PUT"
        ]

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Trading AI Daily Recommendation Report</title>
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

<h1>Trading AI Daily Recommendation Report</h1>

<div class="card">
    <h2>Summary</h2>
    <div class="metric"><strong>Date</strong>{metadata.get("date", "")}</div>
    <div class="metric"><strong>Symbols Scanned</strong>{metadata.get("symbols_scanned", "")}</div>
    <div class="metric"><strong>Candidates</strong>{len(candidates)}</div>
    <div class="metric"><strong>Live Profile</strong>{metadata.get("live_profile", "")}</div>
    <div class="metric"><strong>Min Score</strong>{metadata.get("min_score", "")}</div>
    <div class="metric"><strong>Pricing DTE</strong>{metadata.get("pricing_dte", "")}</div>
    <div class="metric"><strong>Open Positions</strong>{portfolio_summary.get("positions", 0)}</div>
</div>

<div class="card">
    <h2>Portfolio Exposure</h2>
    {self.build_table(
        portfolio_rows,
        [
            ("Type", "type"),
            ("Name", "name"),
            ("Positions", "positions"),
        ],
    )}
</div>

<div class="card">
    <h2>All Recommendations</h2>
    {self.build_table(
        rows,
        [
            ("Symbol", "symbol"),
            ("Sector", "sector"),
            ("Signal", "signal"),
            ("Strategy", "strategy"),
            ("Adjusted Score", "adjusted_score"),
            ("Base Score", "final_score"),
            ("Penalty", "portfolio_penalty"),
            ("Portfolio Notes", "portfolio_notes"),
            ("Signal Score", "signal_score"),
            ("Regime", "regime"),
            ("Underlying", "underlying"),
            ("Strike", "strike"),
            ("Option Price", "option_price"),
            ("Delta", "delta"),
            ("Theta", "theta"),
            ("Vega", "vega"),
            ("Vol", "volatility"),
            ("DTE", "dte"),
        ],
    )}
</div>

<div class="card">
    <h2>Top Calls</h2>
    {self.build_table(
        top_calls,
        [
            ("Symbol", "symbol"),
            ("Sector", "sector"),
            ("Adjusted Score", "adjusted_score"),
            ("Base Score", "final_score"),
            ("Penalty", "portfolio_penalty"),
            ("Notes", "portfolio_notes"),
            ("Underlying", "underlying"),
            ("Option Price", "option_price"),
            ("Delta", "delta"),
            ("Theta", "theta"),
            ("Vega", "vega"),
        ],
    )}
</div>

<div class="card">
    <h2>Top Puts</h2>
    {self.build_table(
        top_puts,
        [
            ("Symbol", "symbol"),
            ("Sector", "sector"),
            ("Adjusted Score", "adjusted_score"),
            ("Base Score", "final_score"),
            ("Penalty", "portfolio_penalty"),
            ("Notes", "portfolio_notes"),
            ("Underlying", "underlying"),
            ("Option Price", "option_price"),
            ("Delta", "delta"),
            ("Theta", "theta"),
            ("Vega", "vega"),
        ],
    )}
</div>

</body>
</html>
"""

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(html)

        return path

    def generate(
        self,
        candidates,
        metadata,
        portfolio_summary,
        report_date=None,
    ):
        output_dir = self.run_dir(report_date)

        csv_path = output_dir / "recommendations.csv"
        json_path = output_dir / "recommendations.json"
        html_path = output_dir / "report.html"

        self.export_csv(
            candidates,
            csv_path,
        )

        self.export_json(
            candidates,
            json_path,
            metadata,
            portfolio_summary,
        )

        self.generate_html(
            candidates,
            html_path,
            metadata,
            portfolio_summary,
        )

        return {
            "output_dir": str(output_dir),
            "csv": str(csv_path),
            "json": str(json_path),
            "html": str(html_path),
        }
