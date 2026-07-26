import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from trading_ai.reporting import (
    ReportingContext,
    governance_summary_html,
    published_state_html,
    write_report_manifest,
)


class LiveTradeCandidateReporter:

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

    def _dict(self, trade):

        row = asdict(trade)
        row["portfolio_notes"] = " | ".join(row.get("portfolio_notes", []))
        row["trade_notes"] = " | ".join(row.get("trade_notes", []))
        return row

    def export_csv(self, trades, path):

        fieldnames = [
            "scanner_run_id",
            "candidate_id",
            "market_state_hash",
            "scanner_version",
            "publication_name",
            "ingestion_run_id",
            "publication_status",
            "published_at",
            "market_as_of_date",
            "market_intelligence_snapshot_timestamp",
            "option_snapshot_timestamp",
            "option_snapshot_id",
            "option_snapshot_completeness_pct",
            "published_state_degraded",
            "symbol",
            "signal",
            "strategy",
            "sector",
            "ai_score",
            "base_ai_score",
            "dealer_score_adjustment",
            "dealer_context_status",
            "dealer_snapshot_date",
            "institutional_positioning_score",
            "positioning_label",
            "gamma_regime",
            "gamma_flip",
            "primary_call_wall",
            "primary_put_wall",
            "range_probability",
            "breakout_probability",
            "market_structure_confidence",
            "confidence",
            "underlying_price",
            "strike",
            "expiry",
            "spread_pct",
            "option_volume",
            "open_interest",
            "quote_timestamp",
            "option_data_source",
            "price_source",
            "last_price",
            "ask",
            "bid",
            "contract_ticker",
            "dte",
            "option_entry",
            "target_price",
            "stop_price",
            "contracts",
            "estimated_cost",
            "max_risk",
            "estimated_reward",
            "reward_risk_ratio",
            "delta",
            "gamma",
            "theta",
            "vega",
            "rho",
            "volatility",
            "market_regime",
            "technical_score",
            "greeks_score",
            "regime_score",
            "volatility_score",
            "risk_score",
            "portfolio_penalty",
            "portfolio_notes",
            "ranking_reason",
            "trade_notes",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
            )

            writer.writeheader()

            for trade in trades:
                row = self._dict(trade)
                writer.writerow({
                    key: row.get(key, "")
                    for key in fieldnames
                })

        return path

    def export_json(self, trades, path, metadata):

        context = ReportingContext.from_metadata(metadata)
        payload = {
            "report_version": context.report_version,
            "reporting_context": context.to_dict(),
            "metadata": metadata,
            "trades": [
                self._dict(trade)
                for trade in trades
            ],
        }

        with open(path, "w") as f:
            json.dump(payload, f, indent=2)

        return path

    def build_table(self, rows, columns):

        if not rows:
            return "<p>No live trade candidates.</p>"

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

    def formatted_rows(self, trades):

        rows = []

        for t in trades:
            rows.append({
                "symbol": t.symbol,
                "signal": t.signal,
                "strategy": t.strategy,
                "sector": t.sector,
                "ai_score": f"{t.ai_score:.2f}",
                "base_ai_score": f"{getattr(t, 'base_ai_score', t.ai_score):.2f}",
                "dealer_score_adjustment": f"{getattr(t, 'dealer_score_adjustment', 0.0):+.2f}",
                "dealer_context_status": getattr(t, "dealer_context_status", "MISSING"),
                "dealer_snapshot_date": getattr(t, "dealer_snapshot_date", ""),
                "institutional_positioning_score": f"{getattr(t, 'institutional_positioning_score', 0.0):.2f}",
                "positioning_label": getattr(t, "positioning_label", "UNAVAILABLE"),
                "gamma_regime": getattr(t, "gamma_regime", "UNAVAILABLE"),
                "gamma_flip": getattr(t, "gamma_flip", None),
                "primary_call_wall": getattr(t, "primary_call_wall", None),
                "primary_put_wall": getattr(t, "primary_put_wall", None),
                "range_probability": getattr(t, "range_probability", 0.0),
                "breakout_probability": getattr(t, "breakout_probability", 0.0),
                "market_structure_confidence": getattr(t, "market_structure_confidence", 0.0),
                "confidence": t.confidence,
                "underlying_price": self.money(t.underlying_price),
                "strike": self.money(t.strike),
                "expiry": t.expiry,
                "expiry_source": t.expiry_source,
                "dte": t.dte,
                "option_entry": self.money(t.option_entry),
                "target_price": self.money(t.target_price),
                "stop_price": self.money(t.stop_price),
                "contracts": t.contracts,
                "estimated_cost": self.money(t.estimated_cost),
                "max_risk": self.money(t.max_risk),
                "estimated_reward": self.money(t.estimated_reward),
                "reward_risk_ratio": f"{t.reward_risk_ratio:.2f}",
                "delta": f"{t.delta:.4f}",
                "gamma": f"{t.gamma:.5f}",
                "theta": f"{t.theta:.4f}",
                "vega": f"{t.vega:.4f}",
                "rho": f"{t.rho:.4f}",
                "volatility": self.pct(t.volatility),
                "market_regime": t.market_regime,
                "technical_score": f"{t.technical_score:.2f}",
                "greeks_score": f"{t.greeks_score:.2f}",
                "regime_score": f"{t.regime_score:.2f}",
                "volatility_score": f"{t.volatility_score:.2f}",
                "risk_score": f"{t.risk_score:.2f}",
                "portfolio_penalty": f"{t.portfolio_penalty:.2f}",
                "portfolio_notes": " | ".join(t.portfolio_notes),
                "ranking_reason": t.ranking_reason,
                "trade_notes": " | ".join(t.trade_notes),
            })

        return rows

    def generate_html(self, trades, path, metadata):

        rows = self.formatted_rows(trades)

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Trading AI Live Trade Candidates</title>
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

<h1>Trading AI Live Trade Candidates</h1>

<div class="card">
    <h2>Summary</h2>
    <div class="metric"><strong>Date</strong>{metadata.get("date", "")}</div>
    <div class="metric"><strong>Trade Candidates</strong>{len(trades)}</div>
    <div class="metric"><strong>Capital</strong>{self.money(metadata.get("capital", 0.0))}</div>
    <div class="metric"><strong>Risk / Trade</strong>{self.pct(metadata.get("risk_per_trade_pct", 0.0))}</div>
    <div class="metric"><strong>Max Position</strong>{self.pct(metadata.get("max_position_pct", 0.0))}</div>
    <div class="metric"><strong>Take Profit</strong>{self.pct(metadata.get("take_profit_pct", 0.0))}</div>
    <div class="metric"><strong>Stop Loss</strong>{self.pct(metadata.get("stop_loss_pct", 0.0))}</div>
</div>

<div class="card">
    <h2>Published Market State</h2>
    {published_state_html(ReportingContext.from_metadata(metadata))}
</div>
    <div class="metric"><strong>Ingestion Run</strong>{metadata.get("published_state", {}).get("ingestion_run_id", "")}</div>
    <div class="metric"><strong>Market As-Of</strong>{metadata.get("published_state", {}).get("market_as_of_date", "")}</div>
    <div class="metric"><strong>Market Intelligence</strong>{metadata.get("published_state", {}).get("market_intelligence_snapshot_timestamp", "")}</div>
    <div class="metric"><strong>Option Snapshot</strong>{metadata.get("published_state", {}).get("option_snapshot_id", "")}</div>
    <div class="metric"><strong>Option Coverage</strong>{metadata.get("published_state", {}).get("option_snapshot_completeness_pct", "")}</div>
</div>

<div class="card">
    <h2>Recommended Live Trade Cards</h2>
    {self.build_table(
        rows,
        [
            ("Symbol", "symbol"),
            ("Signal", "signal"),
            ("Confidence", "confidence"),
            ("AI Score", "ai_score"),
            ("Underlying", "underlying_price"),
            ("Strike", "strike"),
                    ("Expiration", "expiry"),
                    ("DTE", "dte"),
                    ("Expiry Source", "expiry_source"),
            ("Entry", "option_entry"),
            ("Target", "target_price"),
            ("Stop", "stop_price"),
            ("Contracts", "contracts"),
            ("Cost", "estimated_cost"),
            ("Max Risk", "max_risk"),
            ("Reward", "estimated_reward"),
            ("R/R", "reward_risk_ratio"),
            ("Delta", "delta"),
            ("Theta", "theta"),
            ("Vega", "vega"),
            ("Regime", "market_regime"),
            ("Notes", "trade_notes"),
        ],
    )}
</div>

<div class="card">
    <h2>Ranking Details</h2>
    {self.build_table(
        rows,
        [
            ("Symbol", "symbol"),
            ("AI Score", "ai_score"),
            ("Technical", "technical_score"),
            ("Greeks", "greeks_score"),
            ("Regime", "regime_score"),
            ("Volatility", "volatility_score"),
            ("Risk", "risk_score"),
            ("Portfolio Penalty", "portfolio_penalty"),
            ("Ranking Reason", "ranking_reason"),
            ("Portfolio Notes", "portfolio_notes"),
        ],
    )}
</div>

<div class="card">
    <h2>Governance Summary</h2>
    {governance_summary_html(ReportingContext.from_metadata(metadata))}
</div>

</body>
</html>
"""

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(html)

        return path

    def generate(
        self,
        trades,
        metadata,
        report_date=None,
    ):
        output_dir = self.run_dir(report_date)

        csv_path = output_dir / "live_trade_candidates.csv"
        json_path = output_dir / "live_trade_candidates.json"
        html_path = output_dir / "live_trade_candidates.html"

        self.export_csv(trades, csv_path)
        self.export_json(trades, json_path, metadata)
        self.generate_html(trades, html_path, metadata)

        context = ReportingContext.from_metadata(metadata)
        manifest_path = write_report_manifest(
            output_dir / "live_trade_report_manifest.json",
            context=context,
            artifacts=[csv_path, json_path, html_path],
            report_type="live_trade_candidates",
            extra={"trade_count": len(trades)},
        )

        return {
            "output_dir": str(output_dir),
            "csv": str(csv_path),
            "json": str(json_path),
            "html": str(html_path),
            "manifest": str(manifest_path),
        }
