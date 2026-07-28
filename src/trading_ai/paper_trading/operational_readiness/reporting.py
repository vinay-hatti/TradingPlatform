from __future__ import annotations

from html import escape
from typing import Any, Mapping


def render_readiness_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Milestone 51 Phase 9 — Operational Readiness",
        "",
        f"**Portfolio:** {payload['portfolio_id']}",
        f"**Mode:** {payload['mode']}",
        f"**Status:** {payload['overall_status']}",
        f"**Overall score:** {payload['overall_score']:.2f}/100",
        f"**Recommendation:** {payload['recommendation']}",
        "",
        "## Category Scorecard",
        "",
        "| Category | Score | Status | Passed | Warned | Failed |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for row in payload.get("category_scores") or ():
        lines.append(
            f"| {row['category']} | {row['score']:.2f} | {row['status']} | "
            f"{row['passed']} | {row['warned']} | {row['failed']} |"
        )
    lines.extend(["", "## Acceptance Controls", ""])
    for row in payload.get("controls") or ():
        lines.append(
            f"- **{row['status']} — {row['control_id']}**: "
            f"{row['title']} ({row['score']:.2f}/100)"
        )
        if row.get("recommendation"):
            lines.append(f"  - Recommendation: {row['recommendation']}")
    lines.extend(["", "## Sign-off", ""])
    sign_off = payload.get("sign_off") or {}
    lines.append(f"- Eligible: {sign_off.get('eligible', False)}")
    lines.append(f"- Conditional: {sign_off.get('conditional', False)}")
    lines.append(f"- Signed: {sign_off.get('signed', False)}")
    return "\n".join(lines) + "\n"


def render_readiness_html(payload: Mapping[str, Any]) -> str:
    categories = "".join(
        "<tr>"
        f"<td>{escape(str(row['category']))}</td>"
        f"<td>{row['score']:.2f}</td>"
        f"<td>{escape(str(row['status']))}</td>"
        f"<td>{row['passed']}</td>"
        f"<td>{row['warned']}</td>"
        f"<td>{row['failed']}</td>"
        "</tr>"
        for row in payload.get("category_scores") or ()
    )
    controls = "".join(
        "<tr>"
        f"<td>{escape(str(row['control_id']))}</td>"
        f"<td>{escape(str(row['category']))}</td>"
        f"<td>{escape(str(row['title']))}</td>"
        f"<td>{escape(str(row['status']))}</td>"
        f"<td>{row['score']:.2f}</td>"
        f"<td>{escape(str(row.get('recommendation') or ''))}</td>"
        "</tr>"
        for row in payload.get("controls") or ()
    )
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Milestone 51 Phase 9 Operational Readiness</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 32px; color: #202124; }}
h1, h2 {{ margin-bottom: 8px; }}
.score {{ font-size: 28px; font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; }}
th, td {{ border: 1px solid #dadce0; padding: 8px; text-align: left; }}
th {{ background: #f1f3f4; }}
</style>
</head>
<body>
<h1>Milestone 51 Phase 9 — Operational Readiness</h1>
<p><strong>Portfolio:</strong> {escape(str(payload['portfolio_id']))}</p>
<p><strong>Status:</strong> {escape(str(payload['overall_status']))}</p>
<p class="score">{payload['overall_score']:.2f}/100</p>
<p>{escape(str(payload['recommendation']))}</p>
<h2>Category Scorecard</h2>
<table><thead><tr><th>Category</th><th>Score</th><th>Status</th>
<th>Passed</th><th>Warned</th><th>Failed</th></tr></thead>
<tbody>{categories}</tbody></table>
<h2>Acceptance Controls</h2>
<table><thead><tr><th>Control</th><th>Category</th><th>Title</th>
<th>Status</th><th>Score</th><th>Recommendation</th></tr></thead>
<tbody>{controls}</tbody></table>
</body>
</html>
"""
