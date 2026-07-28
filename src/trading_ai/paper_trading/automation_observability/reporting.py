from __future__ import annotations

from typing import Any, Mapping


def render_observability_markdown(payload: Mapping[str, Any]) -> str:
    telemetry = payload["telemetry"]
    lines = [
        "# Milestone 51 Phase 7 — Automation Observability",
        "",
        f"**Portfolio:** {payload['portfolio_id']}",
        f"**Status:** {payload['overall_status']}",
        f"**Automation health:** {payload['health_score']:.2f}/100",
        f"**Incidents:** {payload['alert_summary']['incident_count']}",
        "",
        "## Telemetry",
        "",
        f"- Scheduler status: {telemetry['scheduler_status']}",
        f"- Control-plane status: {telemetry['control_plane_status']}",
        f"- Portfolio health: {telemetry['portfolio_health_score']:.2f} "
        f"({telemetry['portfolio_health_grade']})",
        f"- Risk breaches: {telemetry['risk_breach_count']}",
        f"- Failed phases: {telemetry['failed_phases']}",
        f"- Retried phases: {telemetry['retried_phases']}",
        f"- Active orders: {telemetry['active_orders']}",
        f"- Stale orders: {telemetry['stale_orders']}",
        f"- Open positions: {telemetry['open_positions']}",
        f"- Exit candidates: {telemetry['exit_candidates']}",
        f"- Daily P/L: ${telemetry['daily_pnl']:,.2f}",
        f"- Net liquidation value: "
        f"${telemetry['net_liquidation_value']:,.2f}",
        "",
        "## Health Checks",
        "",
    ]
    for row in payload.get("checks") or ():
        lines.append(
            f"- **{row['status']} — {row['code']}**: {row['message']} "
            f"(actual={row['actual']}, expected={row['expected']})"
        )
    lines.extend(["", "## Incidents", ""])
    incidents = payload.get("incidents") or ()
    if incidents:
        for row in incidents:
            lines.append(
                f"- **{row['severity']} — {row['title']}**: "
                f"{row['recommended_action']}"
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"
