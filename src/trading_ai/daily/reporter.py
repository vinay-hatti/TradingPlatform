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

        row = asdict(candidate)

        return row

    def export_json(self, candidates, path, metadata):

        payload = {
            "metadata": metadata,
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
            "signal",
            "strategy",
            "final_score",
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
                "signal": c.signal,
                "strategy": c.strategy,
                "final_score": f"{c.final_score:.2f}",
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

    def generate_html(
        self,
        candidates,
        path,
        metadata,
    ):
        rows = self.formatted_rows(candidates)

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
</div>

<div class="card">
    <h2>All Recommendations</h2>
    {self.build_table(
        rows,
        [
            ("Symbol", "symbol"),
            ("Signal", "signal"),
            ("Strategy", "strategy"),
            ("Final Score", "final_score"),
            ("Signal Score", "signal_score"),
            ("Call", "call_score"),
            ("Put", "put_score"),
            ("Regime", "regime"),
            ("Underlying", "underlying"),
            ("Strike", "strike"),
            ("Option Price", "option_price"),
            ("Expiry", "expiry"),
            ("Delta", "delta"),
            ("Gamma", "gamma"),
            ("Theta", "theta"),
            ("Vega", "vega"),
            ("Rho", "rho"),
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
            ("Final Score", "final_score"),
            ("Signal Score", "signal_score"),
            ("Regime", "regime"),
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
            ("Final Score", "final_score"),
            ("Signal Score", "signal_score"),
            ("Regime", "regime"),
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
        )

        self.generate_html(
            candidates,
            html_path,
            metadata,
        )

        return {
            "output_dir": str(output_dir),
            "csv": str(csv_path),
            "json": str(json_path),
            "html": str(html_path),
        }
