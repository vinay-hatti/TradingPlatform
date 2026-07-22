from __future__ import annotations

import html
from pathlib import Path


def render_console_report(run_profile) -> str:
    return "\n".join(
        [
            "=" * 76,
            "Milestone 35 Phase 5 Step 5 — Cross-Asset Decision Integration",
            "=" * 76,
            f"As-of date          : {run_profile.as_of_date}",
            f"Macro regime       : {run_profile.macro_regime}",
            f"Tactical bias      : {run_profile.tactical_bias}",
            f"Opportunity regime : {run_profile.opportunity_regime}",
            f"Systemic risk      : {run_profile.systemic_risk_level}",
            f"Confidence         : {run_profile.composite_confidence:.6f}",
            f"Governance         : {run_profile.governance_status}",
            f"Output             : {run_profile.output_path}",
        ]
    )


def render_html_report(profile) -> str:
    adjustment = profile.decision_adjustment
    reasons = "".join(
        f"<li>{html.escape(reason)}</li>"
        for reason in profile.governance_reasons
    ) or "<li>None</li>"
    rationale = "".join(
        f"<li>{html.escape(reason)}</li>"
        for reason in adjustment.rationale
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Cross-Asset &amp; Market Structure Intelligence</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 32px; }}
h1, h2 {{ margin-bottom: 8px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
th {{ background: #f3f3f3; }}
.metric {{ font-weight: bold; }}
</style>
</head>
<body>
<h1>Cross-Asset &amp; Market Structure Intelligence</h1>
<p>Milestone 35 Phase 5 — Decision Integration and Phase Closure</p>

<h2>Composite State</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>As-of date</td><td>{profile.as_of_date}</td></tr>
<tr><td>Macro regime</td><td>{profile.macro_regime}</td></tr>
<tr><td>Tactical bias</td><td>{profile.tactical_bias}</td></tr>
<tr><td>Opportunity regime</td><td>{profile.opportunity_regime}</td></tr>
<tr><td>Systemic risk</td><td>{profile.systemic_risk_level}</td></tr>
<tr><td>Composite confidence</td><td>{profile.composite_confidence:.6f}</td></tr>
<tr><td>Governance</td><td>{profile.governance_status.value}</td></tr>
</table>

<h2>Decision Adjustment</h2>
<table>
<tr><th>Adjustment</th><th>Value</th></tr>
<tr><td>Call score</td><td>{adjustment.call_score_adjustment:.6f}</td></tr>
<tr><td>Put score</td><td>{adjustment.put_score_adjustment:.6f}</td></tr>
<tr><td>Confidence multiplier</td><td>{adjustment.confidence_multiplier:.6f}</td></tr>
<tr><td>Position-size multiplier</td><td>{adjustment.position_size_multiplier:.6f}</td></tr>
<tr><td>Allow new risk</td><td>{adjustment.allow_new_risk}</td></tr>
<tr><td>Preferred direction</td><td>{adjustment.preferred_direction}</td></tr>
</table>

<h2>Governance Reasons</h2>
<ul>{reasons}</ul>

<h2>Decision Rationale</h2>
<ul>{rationale}</ul>
</body>
</html>
'''


def write_html_report(path, profile) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html_report(profile), encoding="utf-8")
    return output
