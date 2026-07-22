from __future__ import annotations

import html
from pathlib import Path


def render_console_report(profile) -> str:
    return "\n".join(
        [
            "=" * 72,
            "Milestone 35 Phase 4 Step 5 — Phase Closure",
            "=" * 72,
            f"As-of date           : {profile.as_of_date}",
            f"Phase status         : {profile.phase_status}",
            f"Artifacts required   : {len(profile.required_artifacts)}",
            f"Artifacts existing   : {len(profile.existing_artifacts)}",
            f"Artifacts missing    : {len(profile.missing_artifacts)}",
            f"Execution steps      : {len(profile.execution_results)}",
            (
                "Reasons              : "
                + (
                    "; ".join(profile.phase_reasons)
                    if profile.phase_reasons
                    else "None"
                )
            ),
        ]
    )


def render_html_report(profile) -> str:
    rows = []
    for result in profile.execution_results:
        rows.append(
            "<tr>"
            f"<td>{html.escape(result.step_name)}</td>"
            f"<td>{html.escape(result.status.value)}</td>"
            f"<td>{'' if result.return_code is None else result.return_code}</td>"
            "</tr>"
        )

    artifact_rows = []
    existing = set(profile.existing_artifacts)
    for artifact in profile.required_artifacts:
        status = "PRESENT" if artifact in existing else "MISSING"
        artifact_rows.append(
            "<tr>"
            f"<td>{html.escape(artifact)}</td>"
            f"<td>{status}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Milestone 35 Phase 4 Closure</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
    th {{ background: #f2f2f2; }}
  </style>
</head>
<body>
  <h1>Milestone 35 Phase 4 Closure</h1>
  <p><strong>As-of date:</strong> {profile.as_of_date}</p>
  <p><strong>Phase status:</strong> {html.escape(profile.phase_status)}</p>

  <h2>Execution Results</h2>
  <table>
    <thead><tr><th>Step</th><th>Status</th><th>Return Code</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>

  <h2>Required Artifacts</h2>
  <table>
    <thead><tr><th>Artifact</th><th>Status</th></tr></thead>
    <tbody>{''.join(artifact_rows)}</tbody>
  </table>
</body>
</html>
"""


def write_html_report(path, profile) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html_report(profile), encoding="utf-8")
    return output
