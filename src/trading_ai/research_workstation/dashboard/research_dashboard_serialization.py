from __future__ import annotations
import html, json
from dataclasses import asdict
from pathlib import Path
from typing import Any

def _jsonable(v: Any) -> Any:
    if hasattr(v,'isoformat'): return v.isoformat()
    if isinstance(v,dict): return {str(k):_jsonable(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [_jsonable(x) for x in v]
    return v

def research_dashboard_payload(profile) -> dict[str,Any]: return _jsonable(asdict(profile))

def write_research_dashboard_json(profile, output_file: str|Path) -> Path:
    p=Path(output_file); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(research_dashboard_payload(profile),indent=2,sort_keys=True)+'\n',encoding='utf-8'); return p

def write_dashboard_summary(profile, output_file: str|Path) -> Path:
    p=Path(output_file); p.parent.mkdir(parents=True,exist_ok=True)
    payload={'dashboard_id':profile.dashboard_id,'case_id':profile.case_id,'symbol':profile.symbol,
      'strategy_name':profile.strategy_name,'recommendation':profile.executive_summary.recommendation,
      'research_status':profile.executive_summary.research_status,'overall_score':profile.scorecard.overall_score,
      'overall_grade':profile.scorecard.overall_grade,'institutional_ready':profile.scorecard.institutional_ready,
      'phase_completion':_jsonable(asdict(profile.phase_completion))}
    p.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8'); return p

def write_research_dashboard_html(profile, output_file: str|Path) -> Path:
    p=Path(output_file); p.parent.mkdir(parents=True,exist_ok=True)
    e=html.escape
    kpis=''.join(f'<div class="card"><h3>{e(k.name)}</h3><strong>{k.score:.1%} ({e(k.grade)})</strong><p>{e(k.explanation)}</p></div>' for k in profile.scorecard.kpis)
    sections=''.join(f'<section><h2>{e(s.title)}</h2><p><b>Status:</b> {e(s.status)}</p><p>{e(s.summary)}</p></section>' for s in profile.sections)
    doc=f"""<!doctype html><html><head><meta charset="utf-8"><title>Research Dashboard</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;line-height:1.45}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.card,section{{border:1px solid #ccc;border-radius:8px;padding:16px;margin:10px 0}}.ready{{font-size:1.2rem;font-weight:bold}}</style></head><body>
<h1>Institutional Research Dashboard</h1><p>{e(profile.symbol)} — {e(profile.strategy_name)}</p>
<p class="ready">Phase status: {e(profile.phase_completion.phase_status)} | Institutional score: {profile.scorecard.overall_score:.1%} ({e(profile.scorecard.overall_grade)})</p>
<h2>Executive Summary</h2><p><b>Recommendation:</b> {e(profile.executive_summary.recommendation)}</p><p>{e(profile.executive_summary.confidence_summary)}</p><p>{e(profile.executive_summary.executive_conclusion)}</p>
<h2>Institutional KPIs</h2><div class="grid">{kpis}</div>{sections}</body></html>"""
    p.write_text(doc,encoding='utf-8'); return p
