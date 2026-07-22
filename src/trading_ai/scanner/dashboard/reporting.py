from __future__ import annotations
from html import escape
from pathlib import Path
from .contracts import DashboardSnapshot

def render_dashboard_html(s:DashboardSnapshot)->str:
    rows=''.join(f'<tr><td>{r.rank}</td><td>{escape(r.symbol)}</td><td>{r.institutional_score:.4f}</td><td>{r.probability_score:.4f}</td><td>{"" if r.expected_move is None else f"{r.expected_move:.4f}"}</td><td>{escape(r.regime or "")}</td></tr>' for r in s.rankings) or '<tr><td colspan="6">No rankings available</td></tr>'
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>Institutional Scanner Dashboard</title><style>body{{font-family:Arial,sans-serif;margin:2rem}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem}}.card{{border:1px solid #ddd;border-radius:8px;padding:1rem}}table{{border-collapse:collapse;width:100%;margin-top:1.5rem}}th,td{{border-bottom:1px solid #ddd;padding:.6rem;text-align:left}}</style></head><body><h1>Institutional Scanner Dashboard</h1><div class="grid"><div class="card"><strong>Status</strong><br>{s.session.status.value}</div><div class="card"><strong>Universe</strong><br>{escape(s.session.universe_name or '')}</div><div class="card"><strong>Completion</strong><br>{s.progress.completion_pct:.2f}%</div><div class="card"><strong>Rankings</strong><br>{len(s.rankings)}</div></div><table><thead><tr><th>Rank</th><th>Symbol</th><th>Institutional Score</th><th>Probability</th><th>Expected Move</th><th>Regime</th></tr></thead><tbody>{rows}</tbody></table></body></html>'''
def write_dashboard_html(path:Path,s:DashboardSnapshot)->Path:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(render_dashboard_html(s),encoding='utf-8'); return path
