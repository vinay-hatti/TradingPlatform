from __future__ import annotations

from html import escape
from typing import Any

from .context import ReportingContext


def _display(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return escape(str(value))


def published_state_html(context: ReportingContext) -> str:
    c = context.to_dict()
    fields = [
        ("Publication", c["publication_name"]),
        ("Status", c["publication_status"]),
        ("Published", c["published_at"]),
        ("Market Date", c["market_as_of_date"]),
        ("Ingestion Run", c["ingestion_run_id"]),
        ("Scanner Run", c["scanner_run_id"]),
        ("Decision Run", c["decision_run_id"]),
        ("Scanner Ready", c["scanner_ready"]),
        ("Decision Ready", c["decision_context_ready"]),
        ("Option Snapshot", c["option_snapshot_id"]),
        ("Option Snapshot Time", c["option_snapshot_timestamp"]),
        ("Market Intelligence", c["market_intelligence_snapshot_timestamp"]),
        ("Option Coverage %", c["option_snapshot_completeness_pct"]),
        ("Market State Hash", c["market_state_hash"]),
    ]
    return "\n".join(
        f'<div class="metric"><strong>{escape(label)}</strong>{_display(value)}</div>'
        for label, value in fields
    )


def governance_summary_html(context: ReportingContext) -> str:
    c = context.to_dict()
    fields = [
        ("Report Version", c["report_version"]),
        ("Scanner Version", c["scanner_version"]),
        ("Decision Version", c["decision_engine_version"]),
        ("Policy Version", c["policy_version"]),
        ("Degraded State", c["published_state_degraded"]),
        ("Generated At", c["generated_at"]),
    ]
    return "\n".join(
        f'<div class="metric"><strong>{escape(label)}</strong>{_display(value)}</div>'
        for label, value in fields
    )
