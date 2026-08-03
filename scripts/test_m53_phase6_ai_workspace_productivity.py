from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pages = (ROOT / "ui/workstation/src/pages.tsx").read_text()
styles = (ROOT / "ui/workstation/src/styles.css").read_text()

required = [
    "type SavedOptionScannerWorkspace",
    "type OpportunityHandoff",
    "trading-ai:option-scanner:saved-workspaces",
    "Explain configuration",
    "Scan diagnostics",
    "pre_filter_count",
    "post_filter_count",
    "trading-ai:opportunity-handoff:current",
    "trading-ai:opportunity-handoff:history",
    "Stage opportunity",
    "snapshotTimestamp:snapshot.timestamp",
    "scannerRunId:selected?.run_id||null",
    "refresh_mode:persistedOnly?'cache_only':refreshMode",
    "auto_refresh:persistedOnly?false:autoRefresh",
]
for token in required:
    assert token in pages, f"missing Phase 6 contract token: {token}"

assert "option-productivity-grid" in styles
assert "opportunity-handoff" in styles
assert "scan-diagnostics-grid" in styles
assert pages.count("Run market ingestion") == 1, "Daily Scanner ingestion must remain singular and unchanged"
assert "{isOptionWorkspace&&<Card title=\"Workspace productivity\">" in pages
assert "{isOptionWorkspace&&<Card title=\"Scan diagnostics\">" in pages
print("Milestone 53 Phase 6 AI workspace and productivity assertions passed.")
