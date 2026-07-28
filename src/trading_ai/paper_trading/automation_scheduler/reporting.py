from __future__ import annotations

from typing import Any, Mapping


def render_scheduler_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Milestone 51 Phase 6 — Scheduled Automation Run",
        "",
        f"**Run ID:** {payload['run_id']}",
        f"**Run key:** {payload['run_key']}",
        f"**Schedule:** {payload['schedule_name']}",
        f"**Portfolio:** {payload['portfolio_id']}",
        f"**Mode:** {payload['mode']}",
        f"**Status:** {payload['status']}",
        "",
        "## Phase Executions",
        "",
    ]
    for row in payload.get("executions") or ():
        lines.append(
            f"- Phase {row['phase']} — {row['name']}: "
            f"**{row['status']}**, attempts {row['attempt_count']}, "
            f"duration {row['duration_seconds']:.2f}s"
        )
    if not payload.get("executions"):
        lines.append("- No phases executed.")
    lines.extend(["", "## Summary", ""])
    for key, value in (payload.get("summary") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Errors", ""])
    errors = payload.get("errors") or ()
    if errors:
        for value in errors:
            lines.append(f"- {value}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"
