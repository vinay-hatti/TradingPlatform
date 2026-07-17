from __future__ import annotations

from dataclasses import asdict
from html import escape
import json
from pathlib import Path


class FinalProjectClosureReportBuilder:
    SECTIONS = (
        "Executive Production Readiness Summary",
        "End-to-End Regression",
        "Performance Benchmarks",
        "Deployment and Rollback Readiness",
        "Operational Governance and Observability",
        "Release Documentation",
        "Final Sign-Off",
        "Project Closure Decision",
    )

    def build_html(self, result) -> str:
        checks = "".join(
            "<tr>"
            f"<td>{escape(item.check_id)}</td>"
            f"<td>{escape(item.category)}</td>"
            f"<td>{item.required}</td>"
            f"<td>{item.passed}</td>"
            f"<td>{item.score:.3f}</td>"
            f"<td>{escape(item.summary)}</td>"
            f"<td>{escape(item.recommendation)}</td>"
            "</tr>"
            for item in result.checks
        )
        benchmarks = "".join(
            "<tr>"
            f"<td>{escape(item.benchmark_id)}</td>"
            f"<td>{escape(item.metric_name)}</td>"
            f"<td>{item.observed_value}</td>"
            f"<td>{item.comparison}</td>"
            f"<td>{item.threshold_value}</td>"
            f"<td>{item.passed}</td>"
            "</tr>"
            for item in result.benchmarks
        )
        regressions = "".join(
            "<tr>"
            f"<td>{escape(item.suite_name)}</td>"
            f"<td>{item.total_tests}</td>"
            f"<td>{item.passed_tests}</td>"
            f"<td>{item.failed_tests}</td>"
            f"<td>{item.skipped_tests}</td>"
            f"<td>{item.pass_rate:.3f}</td>"
            f"<td>{item.passed}</td>"
            "</tr>"
            for item in result.regressions
        )
        signoff = (
            escape(str(asdict(result.sign_off)))
            if result.sign_off else "No sign-off"
        )

        return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Trading AI Platform Final Project Closure</title>
<style>
body{{font-family:Arial;margin:32px;color:#18212f}}
h1{{margin-bottom:4px}}
h2{{margin-top:30px;border-bottom:1px solid #ccd4df;padding-bottom:8px}}
table{{border-collapse:collapse;width:100%;margin:14px 0}}
th,td{{border:1px solid #ccd4df;padding:8px;text-align:left;font-size:13px}}
th{{background:#f3f6f9}}
.ready{{font-size:24px;font-weight:bold}}
</style></head><body>
<h1>Trading AI Platform — Final Project Closure</h1>
<h2>{self.SECTIONS[0]}</h2>
<p class="ready">Decision: {escape(result.recommendation)}</p>
<p>Overall score: {result.overall_score:.4f}</p>
<p>Regression pass rate: {result.regression_pass_rate:.4f}</p>
<p>Benchmark pass rate: {result.benchmark_pass_rate:.4f}</p>
<p>Documentation score: {result.documentation_score:.4f}</p>

<h2>{self.SECTIONS[1]}</h2>
<table><tr><th>Suite</th><th>Total</th><th>Passed</th><th>Failed</th><th>Skipped</th><th>Pass Rate</th><th>Passed</th></tr>{regressions}</table>

<h2>{self.SECTIONS[2]}</h2>
<table><tr><th>ID</th><th>Metric</th><th>Observed</th><th>Comparison</th><th>Threshold</th><th>Passed</th></tr>{benchmarks}</table>

<h2>{self.SECTIONS[3]}</h2>
<h2>{self.SECTIONS[4]}</h2>
<h2>{self.SECTIONS[5]}</h2>
<table><tr><th>ID</th><th>Category</th><th>Required</th><th>Passed</th><th>Score</th><th>Summary</th><th>Recommendation</th></tr>{checks}</table>

<h2>{self.SECTIONS[6]}</h2>
<pre>{signoff}</pre>

<h2>{self.SECTIONS[7]}</h2>
<p>Ready for production: {result.ready_for_production}</p>
<p>Critical findings: {result.critical_findings}</p>
<p>High findings: {result.high_findings}</p>
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
