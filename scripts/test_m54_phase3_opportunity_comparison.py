from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel: str) -> str:
    return (ROOT / rel).read_text()

service = text('src/trading_ai/opportunity_domain/service.py')
repo = text('src/trading_ai/opportunity_domain/repository.py')
router = text('src/trading_ai/opportunity_domain/router.py')
page = text('ui/workstation/src/pages.tsx')
api = text('ui/workstation/src/api.ts')

assert 'def designate_preferred' in service
assert 'list_cohort' in repo
assert 'PREFERRED_DESIGNATION_CHANGED' in service
assert '/{opportunity_id}/preferred' in router
assert 'expected_version' in router
assert 'designatePreferred' in api
assert 'Opportunity comparison' in page
assert 'Compare supports up to four opportunities' in page
assert 'MIXED SNAPSHOTS' in page
assert 'Designate preferred' in page
assert "['delta']" in page and "['gamma']" in page and "['theta']" in page and "['vega']" in page
print('Milestone 54 Phase 3 opportunity comparison assertions passed.')
