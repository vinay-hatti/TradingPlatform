from __future__ import annotations

from typing import Any, Mapping


def render_recovery_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Milestone 51 Phase 8 — Automation Recovery",
        "",
        f"**Recovery ID:** {payload['recovery_id']}",
        f"**Portfolio:** {payload['portfolio_id']}",
        f"**Source run:** {payload['source_run_key']}",
        f"**Status:** {payload['status']}",
        "",
        "## Checkpoints",
        "",
    ]
    for row in payload.get("checkpoints") or ():
        lines.append(
            f"- Phase {row['phase']}: **{row['status']}**, "
            f"completed={row['completed']}, checksum={row['checksum'] or 'N/A'}"
        )
    if not payload.get("checkpoints"):
        lines.append("- None")
    lines.extend(["", "## Recovery Actions", ""])
    for row in payload.get("actions") or ():
        lines.append(
            f"- {row['sequence']}. **{row['action_code']}** "
            f"(phase {row['phase']}): {row['reason']}; "
            f"safe_to_replay={row['safe_to_replay']}"
        )
    if not payload.get("actions"):
        lines.append("- None")
    verification = payload.get("verification") or {}
    lines.extend(
        [
            "",
            "## Verification",
            "",
            f"- Scheduler completed: "
            f"{verification.get('scheduler_completed', False)}",
            f"- Observability healthy: "
            f"{verification.get('observability_healthy', False)}",
            f"- Recovery verified: "
            f"{verification.get('recovery_verified', False)}",
        ]
    )
    return "\n".join(lines) + "\n"
