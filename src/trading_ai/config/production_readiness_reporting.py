from __future__ import annotations

from dataclasses import asdict, is_dataclass
from html import escape
from pathlib import Path
from typing import Any


class ProductionReadinessReport:
    """HTML reporting for Milestone 30 Phase 1 operational controls."""

    def _value(self, obj: Any, name: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    def _dict(self, obj: Any) -> dict[str, Any]:
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return dict(obj)
        if is_dataclass(obj):
            return asdict(obj)
        if hasattr(obj, "to_dict"):
            return dict(obj.to_dict())
        return {}

    @staticmethod
    def _fmt(value: Any, default: str = "N/A") -> str:
        if value in (None, ""):
            return default
        return escape(str(value))

    @staticmethod
    def _score(value: Any) -> str:
        try:
            return f"{float(value):.2f}"
        except Exception:
            return "N/A"

    @staticmethod
    def _status_class(allowed: bool) -> str:
        return "positive" if allowed else "negative"

    def _table(self, rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
        if not rows:
            return "<p class='section-note'>No data available.</p>"
        html = "<table><thead><tr>"
        for label, _ in columns:
            html += f"<th>{escape(label)}</th>"
        html += "</tr></thead><tbody>"
        for row in rows:
            html += "<tr>"
            for _, key in columns:
                html += f"<td>{row.get(key, '')}</td>"
            html += "</tr>"
        html += "</tbody></table>"
        return html

    def readiness_summary_html(self, readiness: Any) -> str:
        if readiness is None:
            return """
<div class="card">
<h2>Startup Readiness Gate</h2>
<p class="section-note">No startup-readiness profile is available.</p>
</div>
"""
        allowed = bool(self._value(readiness, "allowed", False))
        return f"""
<div class="card">
<h2>Startup Readiness Gate</h2>
<div class="metric"><strong>Environment</strong>{self._fmt(self._value(readiness, 'environment'))}</div>
<div class="metric"><strong>Allowed</strong><span class="{self._status_class(allowed)}">{'YES' if allowed else 'NO'}</span></div>
<div class="metric"><strong>Score</strong>{self._score(self._value(readiness, 'score'))}</div>
<div class="metric"><strong>Grade</strong>{self._fmt(self._value(readiness, 'grade'))}</div>
<div class="metric"><strong>Severity</strong>{self._fmt(self._value(readiness, 'severity'))}</div>
<div class="metric"><strong>Decision</strong>{self._fmt(self._value(readiness, 'recommendation'))}</div>
<div class="metric"><strong>Active Version</strong>{self._fmt(self._value(readiness, 'active_environment_version'))}</div>
<div class="metric"><strong>Runtime Score</strong>{self._score(self._value(readiness, 'runtime_score'))}</div>
<div class="metric"><strong>Environment Score</strong>{self._score(self._value(readiness, 'environment_score'))}</div>
<div class="metric"><strong>Secret Score</strong>{self._score(self._value(readiness, 'secret_score'))}</div>
</div>
"""

    def readiness_checks_html(self, readiness: Any) -> str:
        rows = []
        for check in self._value(readiness, "checks", ()) or ():
            passed = bool(self._value(check, "passed", False))
            rows.append({
                "name": self._fmt(self._value(check, "name")),
                "category": self._fmt(self._value(check, "category")),
                "required": "YES" if bool(self._value(check, "required", False)) else "NO",
                "passed": f"<span class='{self._status_class(passed)}'>{'YES' if passed else 'NO'}</span>",
                "score": self._score(self._value(check, "score")),
                "severity": self._fmt(self._value(check, "severity")),
                "message": self._fmt(self._value(check, "message")),
            })
        return f"""
<div class="card">
<h2>Startup Gate Controls</h2>
{self._table(rows, [
    ('Control', 'name'), ('Category', 'category'), ('Required', 'required'),
    ('Passed', 'passed'), ('Score', 'score'), ('Severity', 'severity'),
    ('Message', 'message'),
])}
</div>
"""

    def runtime_checks_html(self, readiness: Any) -> str:
        runtime = self._value(readiness, "runtime_profile", None)
        rows = []
        for check in self._value(runtime, "checks", ()) or ():
            passed = bool(self._value(check, "passed", False))
            rows.append({
                "name": self._fmt(self._value(check, "name")),
                "category": self._fmt(self._value(check, "category")),
                "passed": f"<span class='{self._status_class(passed)}'>{'YES' if passed else 'NO'}</span>",
                "severity": self._fmt(self._value(check, "severity")),
                "message": self._fmt(self._value(check, "message")),
            })
        return f"""
<div class="card">
<h2>Runtime Safety Controls</h2>
{self._table(rows, [
    ('Control', 'name'), ('Category', 'category'), ('Passed', 'passed'),
    ('Severity', 'severity'), ('Message', 'message'),
])}
</div>
"""

    def secret_health_html(self, readiness: Any) -> str:
        secrets = self._value(readiness, "secret_profile", None)
        rows = []
        for item in self._value(secrets, "credentials", ()) or ():
            allowed = bool(self._value(item, "allowed", False))
            rows.append({
                "name": self._fmt(self._value(item, "name")),
                "provider": self._fmt(self._value(item, "provider")),
                "resolved": "YES" if bool(self._value(item, "resolved", False)) else "NO",
                "age": self._score(self._value(item, "age_days")),
                "expiry": self._score(self._value(item, "days_until_expiry")),
                "score": self._score(self._value(item, "score")),
                "grade": self._fmt(self._value(item, "grade")),
                "allowed": f"<span class='{self._status_class(allowed)}'>{'YES' if allowed else 'NO'}</span>",
                "recommendation": self._fmt(self._value(item, "recommendation")),
            })
        return f"""
<div class="card">
<h2>Credential Health and Rotation Governance</h2>
{self._table(rows, [
    ('Credential', 'name'), ('Provider', 'provider'), ('Resolved', 'resolved'),
    ('Age Days', 'age'), ('Days to Expiry', 'expiry'), ('Score', 'score'),
    ('Grade', 'grade'), ('Allowed', 'allowed'), ('Recommendation', 'recommendation'),
])}
</div>
"""

    def environment_registry_html(self, readiness: Any) -> str:
        profile = self._value(readiness, "environment_profile", None)
        if not profile:
            return """
<div class="card">
<h2>Environment Configuration Registry</h2>
<p class="section-note">No active environment registry profile is available.</p>
</div>
"""
        allowed = bool(
            self._value(
                profile,
                "allowed",
                self._value(profile, "runtime_allowed", False),
            )
        )
        fingerprint = self._value(
            profile,
            "configuration_fingerprint",
            self._value(profile, "configuration_hash", None),
        )
        return f"""
<div class="card">
<h2>Environment Configuration Registry</h2>
<div class="metric"><strong>Environment</strong>{self._fmt(self._value(profile, 'environment', self._value(profile, 'name')))}</div>
<div class="metric"><strong>Version</strong>{self._fmt(self._value(profile, 'version'))}</div>
<div class="metric"><strong>Active</strong>{'YES' if bool(self._value(profile, 'active', False)) else 'NO'}</div>
<div class="metric"><strong>Runtime Approved</strong><span class="{self._status_class(allowed)}">{'YES' if allowed else 'NO'}</span></div>
<div class="metric"><strong>Runtime Score</strong>{self._score(self._value(profile, 'runtime_score'))}</div>
<div class="metric"><strong>Runtime Grade</strong>{self._fmt(self._value(profile, 'runtime_grade'))}</div>
<div class="metric"><strong>Configuration Fingerprint</strong><code>{self._fmt(fingerprint)}</code></div>
</div>
"""

    def diagnostics_html(self, readiness: Any) -> str:
        warnings = self._value(readiness, "warnings", ()) or ()
        rejections = self._value(readiness, "rejection_reasons", ()) or ()
        warning_html = (
            "<p class='warning'><strong>Warnings:</strong> "
            + ", ".join(escape(str(item)) for item in warnings)
            + "</p>"
            if warnings else
            "<p class='section-note'>No startup warnings.</p>"
        )
        rejection_html = (
            "<p class='negative'><strong>Rejections:</strong> "
            + ", ".join(escape(str(item)) for item in rejections)
            + "</p>"
            if rejections else
            "<p class='positive'><strong>Rejections:</strong> None</p>"
        )
        return f"""
<div class="card">
<h2>Operational Diagnostics</h2>
{warning_html}
{rejection_html}
</div>
"""

    def generate(
        self,
        readiness_profile: Any,
        path: str | Path = "reports/production_readiness.html",
    ) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Production Readiness Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; background:#f4f6f8; color:#1d2733; }}
h1 {{ margin-bottom:4px; }}
.card {{ background:white; border:1px solid #d9e0e7; border-radius:8px; padding:18px; margin:16px 0; }}
.metric {{ display:inline-block; min-width:220px; margin:8px 14px 8px 0; vertical-align:top; }}
.metric strong {{ display:block; color:#52606d; margin-bottom:4px; }}
table {{ border-collapse:collapse; width:100%; margin-top:12px; }}
th,td {{ border:1px solid #d9e0e7; padding:8px; text-align:left; }}
th {{ background:#eef2f6; }}
.positive {{ color:#147d3f; font-weight:bold; }}
.negative {{ color:#b42318; font-weight:bold; }}
.warning {{ color:#9a6700; }}
.section-note {{ color:#66788a; }}
code {{ word-break:break-all; }}
</style>
</head>
<body>
<h1>Production Configuration and Runtime Safety</h1>
<p>Milestone 30, Phase 1 operational readiness report.</p>
{self.readiness_summary_html(readiness_profile)}
{self.readiness_checks_html(readiness_profile)}
{self.runtime_checks_html(readiness_profile)}
{self.environment_registry_html(readiness_profile)}
{self.secret_health_html(readiness_profile)}
{self.diagnostics_html(readiness_profile)}
</body>
</html>
"""
        target.write_text(html, encoding="utf-8")
        return target
