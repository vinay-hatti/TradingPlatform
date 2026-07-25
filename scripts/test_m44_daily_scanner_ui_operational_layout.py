from pathlib import Path

root = Path(__file__).resolve().parents[1]
pages = (root / 'ui/workstation/src/pages.tsx').read_text()
app = (root / 'ui/workstation/src/App.tsx').read_text()
styles = (root / 'ui/workstation/src/styles.css').read_text()

assert 'Provider health and lineage' not in pages
assert 'Data architecture' not in pages
assert 'MILESTONE 43' not in app
assert '<h1>Trading Operations Workstation</h1>' in app
assert 'candidate-table-scroll' in pages
assert 'expandedTrade' in pages
assert 'candidateRankingReason' in pages
assert 'Positive contributors' in pages
assert 'Constraints and penalties' in pages
assert 'Contract selection' in pages
assert 'Data freshness' in pages
assert 'position:sticky' in styles
assert 'white-space:nowrap' in styles
assert '.content{max-width:none' in styles
print('Milestone 44 Daily Scanner UI operational layout assertions passed.')
