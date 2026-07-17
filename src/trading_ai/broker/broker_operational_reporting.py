from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


class BrokerOperationalReport:
    """HTML operational reporting for Milestone 30 Phase 3."""

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
    def _score(value: Any) -> str:
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def _status_class(allowed: bool) -> str:
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

    def readiness_html(self, readiness: Any) -> str:
        if readiness is None:
            return (
                "<div class='card'><h2>Broker Authentication and Readiness</h2>"
                "<p class='note'>No readiness profile supplied.</p></div>"
            )
        allowed = bool(self._value(readiness, "allowed", False))
        account = self._value(readiness, "account", None)
        authentication = self._value(readiness, "authentication", None)
        return f"""
<div class="card">
<h2>Broker Authentication and Readiness</h2>
<div class="metric"><strong>Broker</strong>{self._fmt(self._value(readiness, "broker"))}</div>
<div class="metric"><strong>Environment</strong>{self._fmt(self._value(readiness, "environment"))}</div>
<div class="metric"><strong>Allowed</strong><span class="{self._status_class(allowed)}">{'YES' if allowed else 'NO'}</span></div>
<div class="metric"><strong>Score</strong>{self._score(self._value(readiness, "score"))}</div>
<div class="metric"><strong>Grade</strong>{self._fmt(self._value(readiness, "grade"))}</div>
<div class="metric"><strong>Decision</strong>{self._fmt(self._value(readiness, "recommendation"))}</div>
<div class="metric"><strong>Account</strong>{self._fmt(self._value(account, "account_id"))}</div>
<div class="metric"><strong>Buying Power</strong>{self._score(self._value(account, "buying_power"))}</div>
<div class="metric"><strong>Option Buying Power</strong>{self._score(self._value(account, "option_buying_power"))}</div>
<div class="metric"><strong>Session</strong>{self._fmt(self._value(authentication, "session_id"))}</div>
</div>
"""

    def order_execution_html(self, results: Any) -> str:
        rows: list[dict[str, Any]] = []
        for item in results or ():
            allowed = bool(self._value(item, "allowed", False))
            rows.append(
                {
                    "action": self._fmt(self._value(item, "action")),
                    "client": self._fmt(self._value(item, "client_order_id")),
                    "broker": self._fmt(self._value(item, "broker_order_id")),
                    "status": self._fmt(self._value(item, "status")),
                    "allowed": (
                        f"<span class='{self._status_class(allowed)}'>"
                        f"{'YES' if allowed else 'NO'}</span>"
                    ),
                    "replayed": (
                        "YES" if bool(self._value(item, "replayed", False)) else "NO"
                    ),
                    "score": self._score(self._value(item, "score")),
                    "decision": self._fmt(self._value(item, "recommendation")),
                }
            )
        return f"""
<div class="card">
<h2>Order Submission, Cancellation, Replacement, and Idempotency</h2>
{self._table(rows, [
    ("Action", "action"), ("Client Order", "client"), ("Broker Order", "broker"),
    ("Status", "status"), ("Allowed", "allowed"), ("Replayed", "replayed"),
    ("Score", "score"), ("Decision", "decision"),
])}
</div>
"""

    def order_status_html(self, summaries: Any) -> str:
        rows: list[dict[str, Any]] = []
        for item in summaries or ():
            rows.append(
                {
                    "broker": self._fmt(self._value(item, "broker_order_id")),
                    "client": self._fmt(self._value(item, "client_order_id")),
                    "status": self._fmt(self._value(item, "status")),
                    "ordered": self._score(self._value(item, "ordered_quantity")),
                    "filled": self._score(self._value(item, "filled_quantity")),
                    "remaining": self._score(self._value(item, "remaining_quantity")),
                    "price": self._score(self._value(item, "average_fill_price")),
                    "commission": self._score(self._value(item, "commission")),
                    "fees": self._score(self._value(item, "fees")),
                }
            )
        return f"""
<div class="card">
<h2>Order Status, Fills, Commissions, and Fees</h2>
{self._table(rows, [
    ("Broker Order", "broker"), ("Client Order", "client"), ("Status", "status"),
    ("Ordered", "ordered"), ("Filled", "filled"), ("Remaining", "remaining"),
    ("Average Fill", "price"), ("Commission", "commission"), ("Fees", "fees"),
])}
</div>
"""

    def positions_html(self, reconciliation: Any) -> str:
        rows: list[dict[str, Any]] = []
        profiles = self._value(reconciliation, "position_profiles", ()) or ()
        for item in profiles:
            allowed = bool(self._value(item, "allowed", False))
            broker_position = self._value(item, "broker_position", None)
            platform_position = self._value(item, "platform_position", None)
            rows.append(
                {
                    "symbol": self._fmt(self._value(item, "symbol")),
                    "broker_qty": self._score(self._value(broker_position, "quantity")),
                    "platform_qty": self._score(self._value(platform_position, "quantity")),
                    "qty_diff": self._score(self._value(item, "quantity_difference")),
                    "cost_diff": self._score(
                        self._value(item, "average_cost_difference_pct")
                    ),
                    "score": self._score(self._value(item, "score")),
                    "allowed": (
                        f"<span class='{self._status_class(allowed)}'>"
                        f"{'YES' if allowed else 'NO'}</span>"
                    ),
                    "decision": self._fmt(self._value(item, "recommendation")),
                }
            )
        return f"""
<div class="card">
<h2>Position Synchronization and Reconciliation</h2>
<div class="metric"><strong>Matched</strong>{self._fmt(self._value(reconciliation, "matched_position_count", 0))}</div>
<div class="metric"><strong>Rejected</strong>{self._fmt(self._value(reconciliation, "rejected_position_count", 0))}</div>
<div class="metric"><strong>Score</strong>{self._score(self._value(reconciliation, "score"))}</div>
<div class="metric"><strong>Decision</strong>{self._fmt(self._value(reconciliation, "recommendation"))}</div>
{self._table(rows, [
    ("Symbol", "symbol"), ("Broker Qty", "broker_qty"),
    ("Platform Qty", "platform_qty"), ("Qty Difference", "qty_diff"),
    ("Cost Difference %", "cost_diff"), ("Score", "score"),
    ("Allowed", "allowed"), ("Decision", "decision"),
])}
</div>
"""

    def diagnostics_html(self, *profiles: Any) -> str:
        warnings: list[str] = []
        rejections: list[str] = []
        for profile in profiles:
            if isinstance(profile, (list, tuple)):
                items = profile
            else:
                items = (profile,)
            for item in items:
                warnings.extend(self._value(item, "warnings", ()) or ())
                rejections.extend(
                    self._value(item, "rejection_reasons", ()) or ()
                )
        warning_text = ", ".join(escape(str(item)) for item in warnings) or "None"
        rejection_text = (
            ", ".join(escape(str(item)) for item in rejections) or "None"
        )
        return f"""
<div class="card">
<h2>Broker Operational Diagnostics</h2>
<p class="warning"><strong>Warnings:</strong> {warning_text}</p>
<p class="negative"><strong>Rejections:</strong> {rejection_text}</p>
</div>
"""

    def generate(
        self,
        *,
        readiness_profile: Any = None,
        execution_results: Any = (),
        order_summaries: Any = (),
        reconciliation_summary: Any = None,
        path: str | Path = "reports/broker_operational_report.html",
    ) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Broker Operational Report</title>
<style>
body {{ font-family:Arial,sans-serif; margin:24px; background:#f4f6f8; color:#1d2733; }}
.card {{ background:#fff; border:1px solid #d9e0e7; border-radius:8px; padding:18px; margin:16px 0; }}
.metric {{ display:inline-block; min-width:210px; margin:8px 14px 8px 0; vertical-align:top; }}
.metric strong {{ display:block; color:#52606d; margin-bottom:4px; }}
table {{ width:100%; border-collapse:collapse; margin-top:12px; }}
th,td {{ border:1px solid #d9e0e7; padding:8px; text-align:left; }}
th {{ background:#eef2f6; }}
.positive {{ color:#147d3f; font-weight:bold; }}
.negative {{ color:#b42318; font-weight:bold; }}
.warning {{ color:#9a6700; }}
.note {{ color:#66788a; }}
</style>
</head>
<body>
<h1>Live Broker Integration and Operations</h1>
<p>Milestone 30, Phase 3 operational readiness and reconciliation report.</p>
{self.readiness_html(readiness_profile)}
{self.order_execution_html(execution_results)}
{self.order_status_html(order_summaries)}
{self.positions_html(reconciliation_summary)}
{self.diagnostics_html(readiness_profile, execution_results, reconciliation_summary)}
</body>
</html>
"""
        target.write_text(html, encoding="utf-8")
        return target
