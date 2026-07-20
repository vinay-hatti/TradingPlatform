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
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def knowledge_dashboard_payload(profile) -> dict[str, Any]:
    return _jsonable(asdict(profile))


def write_knowledge_dashboard_json(profile, output_file: str | Path) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(knowledge_dashboard_payload(profile), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_knowledge_dashboard_summary(profile, output_file: str | Path) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dashboard_id": profile.dashboard_id,
        "generated_at": profile.generated_at.isoformat(),
        "milestone": profile.milestone,
        "phase": profile.phase,
        "governance_status": profile.governance_status,
        "readiness_score": profile.readiness_score,
        "readiness_grade": profile.readiness_grade,
        "research_case_count": profile.research_case_count,
        "pattern_cluster_count": profile.pattern_cluster_count,
        "institutional_learning_case_count": profile.institutional_learning_case_count,
        "analyst_count": profile.analyst_count,
        "milestone_complete": profile.metadata.get("milestone_complete", False),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_knowledge_dashboard_html(profile, output_file: str | Path) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    metric_cards = "\n".join(
        f"""
        <section class="card">
          <h3>{html.escape(metric.name)}</h3>
          <div class="metric">{metric.value:.1%}</div>
          <div class="status">{html.escape(metric.status)}</div>
          <p>{html.escape(metric.detail)}</p>
        </section>
        """
        for metric in profile.metrics
    )
    highlights = "".join(f"<li>{html.escape(item)}</li>" for item in profile.highlights)
    risks = "".join(f"<li>{html.escape(item)}</li>" for item in profile.risks)

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Milestone 34 Knowledge Dashboard</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 0; background: #f5f7fa; color: #172033; }}
header {{ background: #172033; color: white; padding: 28px; }}
main {{ padding: 24px; max-width: 1200px; margin: auto; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }}
.card {{ background: white; padding: 18px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
.metric {{ font-size: 32px; font-weight: bold; margin: 8px 0; }}
.status {{ display: inline-block; padding: 4px 8px; border-radius: 6px; background: #e8eef7; }}
.summary {{ margin-top: 22px; }}
table {{ width: 100%; border-collapse: collapse; background: white; }}
th, td {{ padding: 10px; border-bottom: 1px solid #ddd; text-align: left; }}
</style>
</head>
<body>
<header>
  <h1>Milestone 34 — Knowledge Dashboard</h1>
  <p>Phase 5 institutional research intelligence and milestone closure</p>
  <p><strong>Readiness:</strong> {profile.readiness_score:.1%} ({html.escape(profile.readiness_grade)})</p>
  <p><strong>Governance:</strong> {html.escape(profile.governance_status)}</p>
</header>
<main>
  <div class="grid">{metric_cards}</div>
  <section class="card summary">
    <h2>Executive Summary</h2>
    <table>
      <tr><th>Research cases</th><td>{profile.research_case_count}</td></tr>
      <tr><th>Pattern clusters</th><td>{profile.pattern_cluster_count}</td></tr>
      <tr><th>Learning cases</th><td>{profile.institutional_learning_case_count}</td></tr>
      <tr><th>Analysts</th><td>{profile.analyst_count}</td></tr>
    </table>
  </section>
  <section class="card summary"><h2>Highlights</h2><ul>{highlights}</ul></section>
  <section class="card summary"><h2>Risks and Governance</h2><ul>{risks}</ul></section>
</main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")
    return path
