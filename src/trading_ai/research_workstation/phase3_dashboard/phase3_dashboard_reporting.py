from __future__ import annotations

import html
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def phase3_dashboard_payload(profile) -> dict[str, Any]:
    return _jsonable(asdict(profile))


def write_phase3_dashboard_json(
    profile,
    output_file: str | Path,
) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            phase3_dashboard_payload(profile),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def render_phase3_dashboard_html(profile) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value))

    section_html: list[str] = []
    for section in profile.sections:
        metric_rows = "".join(
            (
                "<tr>"
                f"<td>{esc(metric.label)}</td>"
                f"<td>{esc(metric.value)}</td>"
                f"<td>{esc(metric.status)}</td>"
                f"<td>{esc(metric.severity)}</td>"
                f"<td>{esc(metric.description)}</td>"
                "</tr>"
            )
            for metric in section.metrics
        )
        warnings = "".join(
            f"<li>{esc(item)}</li>"
            for item in section.warnings
        ) or "<li>None</li>"
        rejections = "".join(
            f"<li>{esc(item)}</li>"
            for item in section.rejection_reasons
        ) or "<li>None</li>"

        section_html.append(
            "<section class='panel'>"
            f"<h2>{esc(section.title)}</h2>"
            "<div class='summary-grid'>"
            f"<div><strong>Status</strong><span>{esc(section.status)}</span></div>"
            f"<div><strong>Score</strong><span>{section.score:.2f}</span></div>"
            f"<div><strong>Grade</strong><span>{esc(section.grade)}</span></div>"
            "</div>"
            "<table>"
            "<thead><tr>"
            "<th>Metric</th><th>Value</th><th>Status</th>"
            "<th>Severity</th><th>Description</th>"
            "</tr></thead>"
            f"<tbody>{metric_rows}</tbody>"
            "</table>"
            "<div class='two-column'>"
            f"<div><h3>Warnings</h3><ul>{warnings}</ul></div>"
            f"<div><h3>Rejections</h3><ul>{rejections}</ul></div>"
            "</div>"
            "</section>"
        )

    warnings = "".join(
        f"<li>{esc(item)}</li>"
        for item in profile.warnings
    ) or "<li>None</li>"
    rejections = "".join(
        f"<li>{esc(item)}</li>"
        for item in profile.rejection_reasons
    ) or "<li>None</li>"
    remediation = "".join(
        f"<li>{esc(item)}</li>"
        for item in profile.remediation_actions
    ) or "<li>None</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Milestone 34 Phase 3 Dashboard</title>
<style>
body {{
  font-family: Arial, sans-serif;
  margin: 0;
  background: #f4f6f8;
  color: #1f2933;
}}
header {{
  background: #102a43;
  color: white;
  padding: 24px 32px;
}}
main {{
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}}
.panel {{
  background: white;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}}
.summary-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}}
.summary-grid div {{
  background: #eef2f6;
  padding: 12px;
  border-radius: 8px;
}}
.summary-grid strong, .summary-grid span {{
  display: block;
}}
table {{
  width: 100%;
  border-collapse: collapse;
}}
th, td {{
  text-align: left;
  padding: 10px;
  border-bottom: 1px solid #d9e2ec;
}}
.two-column {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}}
.badge {{
  display: inline-block;
  padding: 5px 10px;
  border-radius: 14px;
  background: #d9e2ec;
  color: #102a43;
  font-weight: bold;
}}
</style>
</head>
<body>
<header>
  <h1>Milestone 34 Phase 3 — Institutional Trade Construction</h1>
  <p>{esc(profile.trade_id)} · {esc(profile.symbol)} · {esc(profile.strategy_name)}</p>
</header>
<main>
<section class="panel">
  <h2>Executive Summary</h2>
  <div class="summary-grid">
    <div><strong>Overall Status</strong><span>{esc(profile.overall_status)}</span></div>
    <div><strong>Overall Score</strong><span>{profile.overall_score:.2f}</span></div>
    <div><strong>Overall Grade</strong><span>{esc(profile.overall_grade)}</span></div>
    <div><strong>Risk Severity</strong><span>{esc(profile.risk_severity)}</span></div>
    <div><strong>Execution Allowed</strong><span>{esc(profile.execution_allowed)}</span></div>
    <div><strong>Approval</strong><span>{esc(profile.approval_status)}</span></div>
  </div>
  <p><strong>Recommendation:</strong> {esc(profile.approval_recommendation)}</p>
</section>
{''.join(section_html)}
<section class="panel">
  <h2>Consolidated Governance Outcome</h2>
  <div class="two-column">
    <div><h3>Warnings</h3><ul>{warnings}</ul></div>
    <div><h3>Rejection Reasons</h3><ul>{rejections}</ul></div>
  </div>
  <h3>Remediation Actions</h3>
  <ul>{remediation}</ul>
</section>
</main>
</body>
</html>
"""


def write_phase3_dashboard_html(
    profile,
    output_file: str | Path,
) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_phase3_dashboard_html(profile),
        encoding="utf-8",
    )
    return path
