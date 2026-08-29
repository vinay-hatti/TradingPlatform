from pathlib import Path

root = Path(__file__).resolve().parents[1]
router = (root / "src/trading_ai/opportunity_domain/router.py").read_text()
app = (root / "src/trading_ai/production_api/app.py").read_text()
pages = (root / "ui/workstation/src/pages.tsx").read_text()
api = (root / "ui/workstation/src/api.ts").read_text()
types = (root / "ui/workstation/src/types.ts").read_text()

assert 'prefix="/api/v1/opportunities"' in router
assert '@router.post("/{opportunity_id}/transitions"' in router
assert '@router.get("/{opportunity_id}/events"' in router
assert 'include_router(opportunity_router)' in app
assert "'opportunities'" in types
assert 'Institutional Opportunity Workspace' in pages
assert 'Opportunity inbox' in pages
assert 'Audit trail' in pages
assert 'opportunityApi.stage' in pages
assert 'trading-ai:opportunity-handoff:history' not in pages
assert 'OPPORTUNITY_ROOT' in api
assert 'expected_version' in api
print("Milestone 54 Phase 2 institutional Opportunity workspace assertions passed.")
