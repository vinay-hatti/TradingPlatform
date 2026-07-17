from __future__ import annotations
from dataclasses import asdict
from html import escape
from pathlib import Path
import json

class DeploymentAutomationReportBuilder:
    def build_html(self, result) -> str:
        raw = asdict(result)
        rows = "".join(
            f"<tr><th>{escape(str(k))}</th><td>{escape(str(v))}</td></tr>"
            for k, v in raw.items() if k != "stages"
        )
        stages = "".join(
            f"<tr><td>{escape(x.stage_name)}</td><td>{escape(x.status)}</td>"
            f"<td>{escape(x.message)}</td><td>{escape(str(x.details))}</td></tr>"
            for x in result.stages
        )
        return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Deployment Automation Report</title>
<style>body{{font-family:Arial;margin:32px}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:8px;text-align:left}}th{{background:#f4f6f8}}</style>
</head><body><h1>Deployment Automation Report</h1>
<table>{rows}</table><h2>Stages</h2>
<table><tr><th>Stage</th><th>Status</th><th>Message</th><th>Details</th></tr>{stages}</table>
</body></html>"""

    def write_html(self, path, result):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.build_html(result), encoding="utf-8")
        return target

    def write_json(self, path, result):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target
