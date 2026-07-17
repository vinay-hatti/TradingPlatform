from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


class RiskGatewayOperationalReport:
    """HTML operational report for Milestone 30 Phase 5."""

    @staticmethod
    def _value(obj: Any, name: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    @staticmethod
    def _fmt(value: Any, default: str = "N/A") -> str:
        if value in (None, ""):
            return default
        return escape(str(value))

    @staticmethod
    def _number(value: Any) -> str:
        try:
            return f"{float(value):,.2f}"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def _class(allowed: bool) -> str:
        return "positive" if allowed else "negative"

    def _table(
        self,
        rows: list[dict[str, Any]],
        columns: list[tuple[str, str]],
    ) -> str:
        if not rows:
            return "<p class='note'>No records available.</p>"
        html = "<table><thead><tr>"
        for label, _ in columns:
            html += f"<th>{escape(label)}</th>"
        html += "</tr></thead><tbody>"
        for row in rows:
            html += "<tr>"
            for _, key in columns:
                html += f"<td>{row.get(key, '')}</td>"
            html += "</tr>"
        return html + "</tbody></table>"

    def summary_html(self, decisions: Any) -> str:
        rows = []
        for item in decisions or ():
            allowed = bool(self._value(item, "allowed", False))
            metadata = self._value(item, "metadata", {}) or {}
            rows.append({
                "aggregate": self._fmt(
                    self._value(item, "aggregate_id")
                ),
                "client": self._fmt(
                    self._value(item, "client_order_id")
                ),
                "account": self._fmt(
                    self._value(item, "account_id")
                ),
                "score": self._number(self._value(item, "score")),
                "grade": self._fmt(self._value(item, "grade")),
                "severity": self._fmt(
                    self._value(item, "severity")
                ),
                "allowed": (
                    f"<span class='{self._class(allowed)}'>"
                    f"{'YES' if allowed else 'NO'}</span>"
                ),
                "recommendation": self._fmt(
                    self._value(item, "recommendation")
                ),
                "blocking": self._fmt(
                    ", ".join(metadata.get("blocking_components", ()))
                    or "None"
                ),
            })
        return f"""
<div class="card">
<h2>Combined Risk-Gateway Decisions</h2>
{self._table(rows, [
    ("Aggregate", "aggregate"), ("Client Order", "client"),
    ("Account", "account"), ("Score", "score"), ("Grade", "grade"),
    ("Severity", "severity"), ("Allowed", "allowed"),
    ("Recommendation", "recommendation"),
    ("Blocking Components", "blocking"),
])}
</div>
"""

    def order_risk_html(self, decisions: Any) -> str:
        rows = []
        for parent in decisions or ():
            item = self._value(parent, "order_level_decision")
            if item is None:
                continue
            exposure = self._value(item, "exposure")
            rows.append({
                "aggregate": self._fmt(
                    self._value(item, "aggregate_id")
                ),
                "notional": self._number(
                    self._value(exposure, "gross_notional")
                ),
                "premium": self._number(
                    self._value(exposure, "gross_premium")
                ),
                "bp": self._number(
                    self._value(exposure, "buying_power_required")
                ),
                "classification": self._fmt(
                    self._value(exposure, "risk_classification")
                ),
                "decision": self._fmt(
                    self._value(item, "recommendation")
                ),
            })
        return f"""
<div class="card">
<h2>Order-Level Notional, Premium, and Buying-Power Risk</h2>
{self._table(rows, [
    ("Aggregate", "aggregate"), ("Gross Notional", "notional"),
    ("Gross Premium", "premium"), ("Buying Power Required", "bp"),
    ("Classification", "classification"), ("Decision", "decision"),
])}
</div>
"""

    def portfolio_html(self, decisions: Any) -> str:
        rows = []
        for parent in decisions or ():
            item = self._value(parent, "portfolio_decision")
            if item is None:
                continue
            exposure = self._value(item, "exposure")
            rows.append({
                "aggregate": self._fmt(
                    self._value(item, "aggregate_id")
                ),
                "gross": self._number(
                    self._value(exposure, "projected_gross_exposure")
                ),
                "net": self._number(
                    self._value(exposure, "projected_net_exposure")
                ),
                "utilization": self._number(
                    100.0 * float(
                        self._value(
                            exposure,
                            "projected_buying_power_utilization",
                            0.0,
                        )
                        or 0.0
                    )
                ) + "%",
                "positions": self._fmt(
                    self._value(exposure, "projected_open_positions")
                ),
                "new": self._fmt(
                    self._value(exposure, "new_positions")
                ),
                "decision": self._fmt(
                    self._value(item, "recommendation")
                ),
            })
        return f"""
<div class="card">
<h2>Portfolio Exposure, Concentration, and Position Limits</h2>
{self._table(rows, [
    ("Aggregate", "aggregate"), ("Projected Gross", "gross"),
    ("Projected Net", "net"), ("Buying-Power Utilization", "utilization"),
    ("Projected Positions", "positions"), ("New Positions", "new"),
    ("Decision", "decision"),
])}
</div>
"""

    def options_html(self, decisions: Any) -> str:
        rows = []
        for parent in decisions or ():
            item = self._value(parent, "options_decision")
            if item is None:
                continue
            greeks = self._value(item, "greeks")
            margin = self._value(item, "margin")
            worst = self._value(item, "worst_scenario")
            rows.append({
                "aggregate": self._fmt(
                    self._value(item, "aggregate_id")
                ),
                "delta": self._number(self._value(greeks, "delta")),
                "gamma": self._number(self._value(greeks, "gamma")),
                "vega": self._number(self._value(greeks, "vega")),
                "worst": self._number(self._value(worst, "loss")),
                "strategy": self._fmt(
                    self._value(margin, "strategy_classification")
                ),
                "margin": self._number(
                    self._value(margin, "margin_required")
                ),
                "decision": self._fmt(
                    self._value(item, "recommendation")
                ),
            })
        return f"""
<div class="card">
<h2>Options Greeks, Scenario Stress, and Strategy Margin</h2>
{self._table(rows, [
    ("Aggregate", "aggregate"), ("Delta", "delta"),
    ("Gamma", "gamma"), ("Vega", "vega"),
    ("Worst Scenario Loss", "worst"), ("Strategy", "strategy"),
    ("Margin Required", "margin"), ("Decision", "decision"),
])}
</div>
"""

    def controls_html(self, decisions: Any) -> str:
        rows = []
        for parent in decisions or ():
            item = self._value(parent, "trading_control_decision")
            if item is None:
                continue
            session = self._value(item, "session")
            state = self._value(item, "control_state")
            kill_switch = self._value(state, "kill_switch")
            rows.append({
                "aggregate": self._fmt(
                    self._value(item, "aggregate_id")
                ),
                "realized": self._number(
                    self._value(session, "daily_realized_pnl")
                ),
                "unrealized": self._number(
                    self._value(session, "daily_unrealized_pnl")
                ),
                "drawdown": self._number(
                    self._value(session, "intraday_drawdown")
                ),
                "kill": self._fmt(
                    self._value(kill_switch, "active", False)
                ),
                "reduce": self._fmt(
                    self._value(item, "reduce_only", False)
                ),
                "decision": self._fmt(
                    self._value(item, "recommendation")
                ),
            })
        return f"""
<div class="card">
<h2>Daily Loss, Drawdown, Kill-Switch, and Trading Halts</h2>
{self._table(rows, [
    ("Aggregate", "aggregate"), ("Realized P&L", "realized"),
    ("Unrealized P&L", "unrealized"), ("Drawdown", "drawdown"),
    ("Kill Switch", "kill"), ("Reduce Only", "reduce"),
    ("Decision", "decision"),
])}
</div>
"""

    def diagnostics_html(self, decisions: Any) -> str:
        warnings = []
        rejections = []
        for item in decisions or ():
            warnings.extend(self._value(item, "warnings", ()) or ())
            rejections.extend(
                self._value(item, "rejection_reasons", ()) or ()
            )
        return f"""
<div class="card">
<h2>Risk-Gateway Operational Diagnostics</h2>
<p class="warning"><strong>Warnings:</strong> {self._fmt(', '.join(map(str, warnings)) or 'None')}</p>
<p class="negative"><strong>Rejections:</strong> {self._fmt(', '.join(map(str, rejections)) or 'None')}</p>
</div>
"""

    def generate(
        self,
        *,
        decisions: Any = (),
        path: str | Path = "reports/risk_gateway_operational_report.html",
    ) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Risk Gateway Operational Report</title>
<style>
body {{ font-family:Arial,sans-serif; margin:24px; background:#f4f6f8; color:#1d2733; }}
.card {{ background:#fff; border:1px solid #d9e0e7; border-radius:8px; padding:18px; margin:16px 0; }}
table {{ width:100%; border-collapse:collapse; margin-top:12px; }}
th,td {{ border:1px solid #d9e0e7; padding:8px; text-align:left; vertical-align:top; }}
th {{ background:#eef2f6; }}
.positive {{ color:#147d3f; font-weight:bold; }}
.negative {{ color:#b42318; font-weight:bold; }}
.warning {{ color:#9a6700; }}
.note {{ color:#66788a; }}
</style>
</head>
<body>
<h1>Pre-Trade Risk Gateway Operations</h1>
<p>Milestone 30, Phase 5 risk controls, institutional decision integration, and execution-gating report.</p>
{self.summary_html(decisions)}
{self.order_risk_html(decisions)}
{self.portfolio_html(decisions)}
{self.options_html(decisions)}
{self.controls_html(decisions)}
{self.diagnostics_html(decisions)}
</body>
</html>
"""
        target.write_text(html, encoding="utf-8")
        return target
