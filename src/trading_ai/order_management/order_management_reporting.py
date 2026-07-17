from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


class OrderManagementOperationalReport:
    """HTML operational report for Milestone 30 Phase 4."""

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

    def aggregates_html(self, aggregates: Any) -> str:
        rows: list[dict[str, Any]] = []
        for item in aggregates or ():
            terminal = bool(self._value(item, "terminal", False))
            state = self._value(item, "state", "UNKNOWN")
            if state in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}:
                terminal = True
            rows.append(
                {
                    "aggregate": self._fmt(
                        self._value(item, "aggregate_id")
                    ),
                    "client": self._fmt(
                        self._value(item, "client_order_id")
                    ),
                    "account": self._fmt(
                        self._value(item, "account_id")
                    ),
                    "state": self._fmt(state),
                    "version": self._fmt(
                        self._value(item, "version")
                    ),
                    "quantity": self._number(
                        self._value(item, "total_quantity")
                    ),
                    "filled": self._number(
                        self._value(item, "filled_quantity")
                    ),
                    "remaining": self._number(
                        self._value(item, "remaining_quantity")
                    ),
                    "broker": self._fmt(
                        self._value(item, "broker_order_id")
                    ),
                    "terminal": (
                        f"<span class='{'negative' if terminal else 'positive'}'>"
                        f"{'YES' if terminal else 'NO'}</span>"
                    ),
                }
            )
        return f"""
<div class="card">
<h2>Canonical Order Aggregates and Lifecycle</h2>
{self._table(rows, [
    ("Aggregate", "aggregate"), ("Client Order", "client"),
    ("Account", "account"), ("State", "state"), ("Version", "version"),
    ("Quantity", "quantity"), ("Filled", "filled"),
    ("Remaining", "remaining"), ("Broker Order", "broker"),
    ("Terminal", "terminal"),
])}
</div>
"""

    def routing_html(self, workflows: Any) -> str:
        rows: list[dict[str, Any]] = []
        for item in workflows or ():
            routing = self._value(item, "routing_decision", None)
            allowed = bool(self._value(item, "allowed", False))
            rows.append(
                {
                    "action": self._fmt(self._value(item, "action")),
                    "aggregate": self._fmt(
                        self._value(item, "aggregate_id")
                    ),
                    "state": self._fmt(self._value(item, "state")),
                    "version": self._fmt(
                        self._value(item, "aggregate_version")
                    ),
                    "route": self._fmt(
                        self._value(routing, "route_id")
                    ),
                    "broker": self._fmt(
                        self._value(routing, "broker")
                    ),
                    "allowed": (
                        f"<span class='{self._status_class(allowed)}'>"
                        f"{'YES' if allowed else 'NO'}</span>"
                    ),
                    "decision": self._fmt(
                        self._value(item, "recommendation")
                    ),
                }
            )
        return f"""
<div class="card">
<h2>Command Handling, Broker Routing, and Workflow Orchestration</h2>
{self._table(rows, [
    ("Action", "action"), ("Aggregate", "aggregate"),
    ("State", "state"), ("Version", "version"),
    ("Route", "route"), ("Broker", "broker"),
    ("Allowed", "allowed"), ("Decision", "decision"),
])}
</div>
"""

    def persistence_html(
        self,
        *,
        journal_replays: Any = (),
        audit_status: Any = None,
    ) -> str:
        rows: list[dict[str, Any]] = []
        for item in journal_replays or ():
            allowed = bool(self._value(item, "allowed", False))
            rows.append(
                {
                    "aggregate": self._fmt(
                        self._value(item, "aggregate_id")
                    ),
                    "events": self._fmt(
                        self._value(item, "event_count", 0)
                    ),
                    "version": self._fmt(
                        self._value(item, "final_version", 0)
                    ),
                    "state": self._fmt(
                        self._value(item, "final_state")
                    ),
                    "allowed": (
                        f"<span class='{self._status_class(allowed)}'>"
                        f"{'YES' if allowed else 'NO'}</span>"
                    ),
                }
            )
        audit_valid = bool(
            self._value(audit_status, "valid", False)
            if audit_status is not None
            else False
        )
        audit_errors = self._value(audit_status, "errors", ()) or ()
        return f"""
<div class="card">
<h2>Repository, Event Journal, Audit Ledger, and Concurrency</h2>
<div class="metric"><strong>Audit Integrity</strong><span class="{self._status_class(audit_valid)}">{'VALID' if audit_valid else 'INVALID/UNAVAILABLE'}</span></div>
<div class="metric"><strong>Audit Errors</strong>{self._fmt(', '.join(map(str, audit_errors)) or 'None')}</div>
{self._table(rows, [
    ("Aggregate", "aggregate"), ("Events", "events"),
    ("Final Version", "version"), ("Final State", "state"),
    ("Replay Valid", "allowed"),
])}
</div>
"""

    def groups_html(self, groups: Any) -> str:
        rows: list[dict[str, Any]] = []
        for item in groups or ():
            members = self._value(item, "members", ()) or ()
            roles = ", ".join(
                f"{self._value(member, 'aggregate_id')}:{self._value(member, 'role')}"
                for member in members
            )
            rows.append(
                {
                    "group": self._fmt(self._value(item, "group_id")),
                    "type": self._fmt(self._value(item, "group_type")),
                    "account": self._fmt(self._value(item, "account_id")),
                    "root": self._fmt(
                        self._value(item, "root_aggregate_id")
                    ),
                    "state": self._fmt(self._value(item, "state")),
                    "members": self._fmt(roles),
                }
            )
        return f"""
<div class="card">
<h2>Parent/Child, Bracket, and OCO Order Groups</h2>
{self._table(rows, [
    ("Group", "group"), ("Type", "type"), ("Account", "account"),
    ("Root Aggregate", "root"), ("State", "state"),
    ("Members and Roles", "members"),
])}
</div>
"""

    def recovery_html(self, checkpoints: Any) -> str:
        rows: list[dict[str, Any]] = []
        for item in checkpoints or ():
            recoverable = bool(
                self._value(item, "recoverable", False)
            )
            rows.append(
                {
                    "checkpoint": self._fmt(
                        self._value(item, "checkpoint_id")
                    ),
                    "aggregate": self._fmt(
                        self._value(item, "aggregate_id")
                    ),
                    "action": self._fmt(
                        self._value(item, "workflow_action")
                    ),
                    "state": self._fmt(self._value(item, "state")),
                    "completed": self._fmt(
                        ", ".join(
                            self._value(item, "completed_steps", ()) or ()
                        )
                    ),
                    "pending": self._fmt(
                        ", ".join(
                            self._value(item, "pending_steps", ()) or ()
                        )
                    ),
                    "retry": self._fmt(
                        self._value(item, "retry_count", 0)
                    ),
                    "recoverable": (
                        f"<span class='{self._status_class(recoverable)}'>"
                        f"{'YES' if recoverable else 'NO'}</span>"
                    ),
                    "error": self._fmt(
                        self._value(item, "last_error")
                    ),
                }
            )
        return f"""
<div class="card">
<h2>Cancel, Replace, and Recovery Governance</h2>
{self._table(rows, [
    ("Checkpoint", "checkpoint"), ("Aggregate", "aggregate"),
    ("Action", "action"), ("State", "state"),
    ("Completed Steps", "completed"), ("Pending Steps", "pending"),
    ("Retries", "retry"), ("Recoverable", "recoverable"),
    ("Last Error", "error"),
])}
</div>
"""

    def diagnostics_html(self, *profiles: Any) -> str:
        warnings: list[str] = []
        rejections: list[str] = []
        for profile in profiles:
            items = (
                profile
                if isinstance(profile, (list, tuple))
                else (profile,)
            )
            for item in items:
                warnings.extend(
                    self._value(item, "warnings", ()) or ()
                )
                rejections.extend(
                    self._value(item, "rejection_reasons", ()) or ()
                )
        return f"""
<div class="card">
<h2>Order Management Operational Diagnostics</h2>
<p class="warning"><strong>Warnings:</strong> {self._fmt(', '.join(map(str, warnings)) or 'None')}</p>
<p class="negative"><strong>Rejections:</strong> {self._fmt(', '.join(map(str, rejections)) or 'None')}</p>
</div>
"""

    def generate(
        self,
        *,
        aggregates: Any = (),
        workflow_results: Any = (),
        journal_replays: Any = (),
        audit_status: Any = None,
        order_groups: Any = (),
        recovery_checkpoints: Any = (),
        path: str | Path = "reports/order_management_operational_report.html",
    ) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Order Management Operational Report</title>
<style>
body {{ font-family:Arial,sans-serif; margin:24px; background:#f4f6f8; color:#1d2733; }}
.card {{ background:#fff; border:1px solid #d9e0e7; border-radius:8px; padding:18px; margin:16px 0; }}
.metric {{ display:inline-block; min-width:230px; margin:8px 14px 8px 0; vertical-align:top; }}
.metric strong {{ display:block; color:#52606d; margin-bottom:4px; }}
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
<h1>Order Management System Operations</h1>
<p>Milestone 30, Phase 4 lifecycle, routing, persistence, linked-order, and recovery report.</p>
{self.aggregates_html(aggregates)}
{self.routing_html(workflow_results)}
{self.persistence_html(
    journal_replays=journal_replays,
    audit_status=audit_status,
)}
{self.groups_html(order_groups)}
{self.recovery_html(recovery_checkpoints)}
{self.diagnostics_html(
    workflow_results,
    journal_replays,
    recovery_checkpoints,
)}
</body>
</html>
"""
        target.write_text(html, encoding="utf-8")
        return target
