from __future__ import annotations

from dataclasses import asdict
from html import escape
import json
from pathlib import Path


class OperationalGovernanceReportBuilder:
    SECTIONS = (
        "Operational Runbook Readiness",
        "Disaster Recovery Readiness",
        "Compliance Evidence",
        "Production Governance",
        "Open Findings and Recommendations",
    )

    def build_html(self, result) -> str:
        raw = asdict(result)
        summary = "".join(
            f"<tr><th>{escape(key)}</th><td>{escape(str(value))}</td></tr>"
            for key, value in raw.items()
            if key != "findings"
        )
        findings = "".join(
            "<tr>"
            f"<td>{escape(item.finding_id)}</td>"
            f"<td>{escape(item.category)}</td>"
            f"<td>{escape(item.severity)}</td>"
            f"<td>{escape(item.status)}</td>"
            f"<td>{escape(item.summary)}</td>"
            f"<td>{escape(item.recommendation)}</td>"
            "</tr>"
            for item in result.findings
        )
        if not findings:
            findings = (
                "<tr><td colspan='6'>No open findings.</td></tr>"
            )
        return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Operational Governance Report</title>
<style>
body{{font-family:Arial;margin:32px;color:#18212f}}
table{{border-collapse:collapse;width:100%;margin:16px 0}}
th,td{{border:1px solid #ccd4df;padding:8px;text-align:left}}
th{{background:#f3f6f9}}
</style></head><body>
<h1>Operational Governance Report</h1>
<table>{summary}</table>
<h2>{self.SECTIONS[0]}</h2>
<p>Runbook readiness: {result.runbook_ready}; score: {result.runbook_score:.3f}</p>
<h2>{self.SECTIONS[1]}</h2>
<p>DR readiness: {result.dr_ready}; score: {result.dr_score:.3f}</p>
<h2>{self.SECTIONS[2]}</h2>
<p>Compliance readiness: {result.compliance_ready}; score: {result.compliance_score:.3f}</p>
<h2>{self.SECTIONS[3]}</h2>
<p>Production governance readiness: {result.production_governance_ready}</p>
<h2>{self.SECTIONS[4]}</h2>
<table>
<tr><th>ID</th><th>Category</th><th>Severity</th><th>Status</th><th>Summary</th><th>Recommendation</th></tr>
{findings}
</table>
</body></html>"""

    def write_html(self, path, result):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.build_html(result), encoding="utf-8")
        return target

    def write_json(self, path, result):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return target
