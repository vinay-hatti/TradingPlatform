from __future__ import annotations

from dataclasses import asdict
from html import escape
import json
from pathlib import Path


class ReleaseReadinessReportBuilder:
    def build_html(self, result) -> str:
        cards = (
            f"<div class='card'><b>Score</b><span>{result.score:.3f}</span></div>"
            f"<div class='card'><b>Threshold</b><span>{result.threshold:.3f}</span></div>"
            f"<div class='card'><b>Ready</b><span>{result.ready}</span></div>"
            f"<div class='card'><b>Critical</b><span>{result.critical_findings}</span></div>"
        )
        rows = []
        for check in result.checks:
            rows.append(
                '<tr>' + ''.join([
                    f'<td>{escape(check.check_id)}</td>',
                    f'<td>{escape(check.category)}</td>',
                    f'<td>{check.passed}</td>',
                    f'<td>{check.score:.3f}</td>',
                    f'<td>{len(check.findings)}</td>',
                ]) + '</tr>'
            )
        findings = []
        for check in result.checks:
            for finding in check.findings:
                findings.append(
                    '<tr>' + ''.join([
                        f'<td>{escape(finding.severity)}</td>',
                        f'<td>{escape(finding.category)}</td>',
                        f'<td>{escape(finding.summary)}</td>',
                        f'<td>{escape(finding.remediation)}</td>',
                    ]) + '</tr>'
                )
        if not findings:
            findings.append('<tr><td colspan="4">No findings.</td></tr>')
        return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Release Readiness Report</title><style>
body{{font-family:Arial;margin:32px;color:#18212f}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.card{{border:1px solid #ccd4df;border-radius:8px;padding:14px;display:flex;flex-direction:column}}.card span{{font-size:24px}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}th,td{{border:1px solid #d7dde5;padding:8px;text-align:left}}th{{background:#f3f6f9}}</style></head><body>
<h1>Release Validation and Deployment Readiness</h1><p>Release: {escape(result.release_id)} / {escape(result.version)}</p>
<p>Environment: {escape(result.environment)} | Recommendation: {escape(result.recommendation)}</p>
<div class="cards">{cards}</div>
<h2>Validation Checks</h2><table><thead><tr><th>Check</th><th>Category</th><th>Passed</th><th>Score</th><th>Findings</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Findings and Remediation</h2><table><thead><tr><th>Severity</th><th>Category</th><th>Summary</th><th>Remediation</th></tr></thead><tbody>{''.join(findings)}</tbody></table>
</body></html>"""

    def write_html(self, path, result):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.build_html(result), encoding='utf-8')
        return target

    def write_json(self, path, result):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + '\n', encoding='utf-8')
        return target
