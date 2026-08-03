from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pages = (ROOT / "ui/workstation/src/pages.tsx").read_text()
styles = (ROOT / "ui/workstation/src/styles.css").read_text()

required_pages = [
    "type ScannerExperienceMode = 'basic' | 'advanced' | 'professional'",
    "option-scanner-workspace",
    "Option Scanner workspace depth",
    "Opportunity definition",
    "Contract horizon",
    "Data readiness",
    "Ingestion operations",
    "Find Opportunities",
    "!isOptionWorkspace&&<>",
    "trading-ai:${config.workspaceKey}:scan-controls",
    "experienceMode",
]
for token in required_pages:
    assert token in pages, f"Missing Phase 2 page contract: {token}"

required_styles = [
    ".option-scanner-toolbar",
    ".mode-switch",
    ".option-scanner-control-grid",
    ".control-section",
    ".option-scanner-actionbar",
    ".opportunity-action",
]
for token in required_styles:
    assert token in styles, f"Missing Phase 2 style contract: {token}"

# Daily Scanner must retain the legacy control titles and shared API payload.
assert '<Card title="Market ingestion">' in pages
assert '<Card title="Scan controls">' in pages
assert "scannerApi.scan({universe,symbols:selectedSymbols()" in pages
assert "scannerApi.refresh({data_scope:ingestionScope" in pages

print("Milestone 53 Phase 2 Option Scanner workspace assertions passed.")
