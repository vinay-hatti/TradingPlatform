from __future__ import annotations

from typing import Any, Mapping


def render_control_plane_markdown(payload: Mapping[str, Any]) -> str:
    decision = payload["control_decision"]
    summary = payload["consolidated_summary"]
    lines = [
        "# Milestone 51 Phase 5 — Automation Control Plane",
        "",
        f"**Cycle:** {payload['cycle_id']}",
        f"**Portfolio:** {payload['portfolio_id']}",
        f"**Mode:** {payload['mode']}",
        f"**Status:** {payload['status']}",
        f"**Authorized:** {decision['allowed']}",
        f"**Kill switch:** {decision['kill_switch_active']}",
        "",
        "## Phase Readiness",
        "",
    ]
    for phase in payload.get("phases") or ():
        lines.append(
            f"- Phase {phase['phase']} — {phase['name']}: "
            f"**{phase['status']}**"
        )
    lines.extend(
        [
            "",
            "## Consolidated Operating Summary",
            "",
            f"- Phase 1 successful handoffs: "
            f"{summary['phase1']['handoff_succeeded']}",
            f"- Phase 2 active orders: "
            f"{summary['phase2']['active_orders']}",
            f"- Phase 2 executions: "
            f"{summary['phase2']['execution_count']}",
            f"- Phase 3 exit candidates: "
            f"{summary['phase3']['exit_candidates']}",
            f"- Phase 4 health: "
            f"{summary['phase4']['health_score']:.2f} "
            f"({summary['phase4']['health_grade']})",
            f"- Phase 4 risk breaches: "
            f"{summary['phase4']['risk_breach_count']}",
            f"- Net liquidation value: "
            f"${summary['phase4']['net_liquidation_value']:,.2f}",
            f"- Daily P/L: ${summary['phase4']['daily_pnl']:,.2f}",
            "",
            "## Control Reasons",
            "",
        ]
    )
    reasons = decision.get("reason_codes") or ()
    if reasons:
        for reason in reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"
