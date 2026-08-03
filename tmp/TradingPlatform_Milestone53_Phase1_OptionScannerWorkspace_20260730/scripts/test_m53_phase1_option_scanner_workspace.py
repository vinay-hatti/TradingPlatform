from pathlib import Path

root = Path(__file__).resolve().parents[1]
app = (root / "ui/workstation/src/App.tsx").read_text()
pages = (root / "ui/workstation/src/pages.tsx").read_text()
types = (root / "ui/workstation/src/types.ts").read_text()

assert "'option-scanner': OptionScannerPage" in app
assert "OptionScannerPage" in app
assert "['option-scanner', 'Option scanner', Search]" in pages
assert "export function DailyScannerPage()" in pages
assert "export function OptionScannerPage()" in pages
assert "function ScannerWorkspacePage" in pages
assert "workspaceKey: 'daily-scanner'" in pages
assert "workspaceKey: 'option-scanner'" in pages
assert "trading-ai:${config.workspaceKey}:scan-controls" in pages
assert "'option-scanner'" in types
assert "Daily scanner" in pages
assert "Option scanner" in pages
print("Milestone 53 Phase 1 Option Scanner workspace assertions passed.")
