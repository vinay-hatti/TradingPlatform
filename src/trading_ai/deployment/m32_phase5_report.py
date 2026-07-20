from __future__ import annotations

from dataclasses import asdict
from html import escape
import json
from pathlib import Path


class Milestone32ClosureReportBuilder:
    def build_html(self, certification) -> str:
        control_rows = "".join(
            "<tr>"
            f"<td>{escape(item.control_id)}</td>"
            f"<td>{escape(item.category)}</td>"
            f"<td>{escape(item.title)}</td>"
            f"<td>{item.required}</td>"
            f"<td>{item.passed}</td>"
            f"<td>{item.score:.3f}</td>"
            f"<td>{escape(item.recommendation)}</td>"
            "</tr>"
            for item in certification.controls
        )
        runbook_rows = "".join(
            "<tr>"
            f"<td>{escape(item.runbook_id)}</td>"
            f"<td>{escape(item.name)}</td>"
            f"<td>{item.ready}</td>"
            f"<td>{item.score:.3f}</td>"
            f"<td>{len(item.findings)}</td>"
            "</tr>"
            for item in certification.runbooks
        )
        dr_rows = "".join(
            "<tr>"
            f"<td>{escape(item.exercise_id)}</td>"
            f"<td>{escape(item.scenario)}</td>"
            f"<td>{item.observed_rto_minutes:.2f} / {item.target_rto_minutes}</td>"
            f"<td>{item.observed_rpo_minutes:.2f} / {item.target_rpo_minutes}</td>"
            f"<td>{item.passed}</td>"
            "</tr>"
            for item in certification.dr_exercises
        )
        sign_off = (
            escape(json.dumps(asdict(certification.sign_off), sort_keys=True))
            if certification.sign_off
            else "No sign-off"
        )
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Milestone 32 Production Readiness Certification</title>
<style>
body{{font-family:Arial,sans-serif;margin:32px;color:#172033}}
h1,h2{{color:#0b3b66}}
.badge{{display:inline-block;padding:8px 12px;border-radius:6px;background:#e8eef5}}
table{{width:100%;border-collapse:collapse;margin:16px 0 28px}}
th,td{{border:1px solid #ccd5df;padding:8px;text-align:left;vertical-align:top}}
th{{background:#eef3f8}}
</style>
</head>
<body>
<h1>Milestone 32 — Production Readiness Certification & Closure</h1>
<p class="badge">{escape(certification.certification_decision)}</p>
<p><strong>Project:</strong> {escape(certification.project_name)}</p>
<p><strong>Release:</strong> {escape(certification.release_version)}</p>
<p><strong>Environment:</strong> {escape(certification.environment)}</p>
<p><strong>Overall score:</strong> {certification.overall_score:.4f}</p>
<p><strong>Certified:</strong> {certification.certified}</p>
<p><strong>Critical findings:</strong> {certification.critical_findings}</p>
<p><strong>High findings:</strong> {certification.high_findings}</p>

<h2>Production Certification Controls</h2>
<table><thead><tr><th>ID</th><th>Category</th><th>Control</th><th>Required</th><th>Passed</th><th>Score</th><th>Recommendation</th></tr></thead>
<tbody>{control_rows}</tbody></table>

<h2>Operational Runbooks</h2>
<table><thead><tr><th>ID</th><th>Name</th><th>Ready</th><th>Score</th><th>Findings</th></tr></thead>
<tbody>{runbook_rows}</tbody></table>

<h2>Disaster Recovery Exercises</h2>
<table><thead><tr><th>ID</th><th>Scenario</th><th>RTO Observed / Target</th><th>RPO Observed / Target</th><th>Passed</th></tr></thead>
<tbody>{dr_rows}</tbody></table>

<h2>Final Sign-Off</h2>
<pre>{sign_off}</pre>

<h2>Milestone Closure</h2>
<p>Milestone 32 closure decision: <strong>{escape(certification.certification_decision)}</strong></p>
</body></html>"""

    def write_html(self, path, certification):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.build_html(certification), encoding="utf-8")
        return target

    def write_json(self, path, certification):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(asdict(certification), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return target
