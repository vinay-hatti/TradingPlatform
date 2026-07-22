from __future__ import annotations

from html import escape
from pathlib import Path

from .ranking_contracts import RankingPage


def _display(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.4f}"
    return escape(str(value))


def render_rankings_html(page: RankingPage) -> str:
    rows = []
    visible_columns = [column for column in page.columns if column.visible]
    for record in page.records:
        selected = " selected" if page.selected_symbol == record.symbol.upper() else ""
        cells = "".join(f"<td>{_display(getattr(record, column.key))}</td>" for column in visible_columns)
        rows.append(f'<tr class="ranking-row{selected}" data-symbol="{escape(record.symbol)}">{cells}</tr>')
    body = "\n".join(rows) or f'<tr><td colspan="{len(visible_columns)}">No opportunities matched the current view.</td></tr>'
    headers = "".join(
        f'<th data-sort="{escape(column.key)}">{escape(column.label)}</th>' for column in visible_columns
    )
    summary = page.summary
    return f'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Opportunity Rankings</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 2rem; }}
.toolbar {{ display:flex; gap:.75rem; align-items:center; flex-wrap:wrap; margin-bottom:1rem; }}
.cards {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:1rem; margin-bottom:1rem; }}
.card {{ border:1px solid #ddd; border-radius:8px; padding:1rem; }}
table {{ border-collapse:collapse; width:100%; }}
th,td {{ border-bottom:1px solid #ddd; padding:.65rem; text-align:left; }}
th {{ cursor:pointer; }}
.ranking-row {{ cursor:pointer; }}
.ranking-row:hover {{ background:#f4f4f4; }}
.ranking-row.selected {{ outline:2px solid currentColor; }}
</style>
</head>
<body>
<h1>Institutional Opportunity Rankings</h1>
<div class="toolbar">
<input id="search" placeholder="Search symbol, sector, exchange, or regime">
<span>Top {page.query.top_n}</span>
<span>Page {page.query.page} of {page.total_pages}</span>
<span id="selection">Selected: {escape(page.selected_symbol or 'None')}</span>
</div>
<div class="cards">
<div class="card"><strong>Visible</strong><br>{page.filtered_records}</div>
<div class="card"><strong>Avg Institutional</strong><br>{summary.average_institutional_score if summary else 0:.4f}</div>
<div class="card"><strong>Avg Probability</strong><br>{summary.average_probability_score if summary else 0:.4f}</div>
<div class="card"><strong>Optionable</strong><br>{summary.optionable_count if summary else 0}</div>
</div>
<table id="rankings"><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>
<script>
const search = document.getElementById('search');
search.addEventListener('input', () => {{
  const token = search.value.toLowerCase();
  document.querySelectorAll('.ranking-row').forEach(row => {{
    row.style.display = row.innerText.toLowerCase().includes(token) ? '' : 'none';
  }});
}});
document.querySelectorAll('.ranking-row').forEach(row => row.addEventListener('click', () => {{
  document.querySelectorAll('.ranking-row').forEach(item => item.classList.remove('selected'));
  row.classList.add('selected');
  document.getElementById('selection').innerText = 'Selected: ' + row.dataset.symbol;
}}));
</script>
</body>
</html>'''


def write_rankings_html(path: Path, page: RankingPage) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_rankings_html(page), encoding="utf-8")
    return path
