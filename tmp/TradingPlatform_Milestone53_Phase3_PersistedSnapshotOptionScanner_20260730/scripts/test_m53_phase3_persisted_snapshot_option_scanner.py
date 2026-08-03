from pathlib import Path

root = Path(__file__).resolve().parents[1]
pages = (root / "ui/workstation/src/pages.tsx").read_text()
styles = (root / "ui/workstation/src/styles.css").read_text()

assert "Published persisted snapshot" in pages
assert "Option Scanner is read-only" in pages
assert "refresh_mode:persistedOnly?'cache_only':refreshMode" in pages
assert "auto_refresh:persistedOnly?false:autoRefresh" in pages
assert "Persisted snapshot only" in pages
assert "No provider calls or ingestion" in pages
assert "Cache-only execution enforced" in pages
assert "snapshot-status" in styles
assert "snapshot-fresh" in styles

option_block = pages.split("{isOptionWorkspace&&<>", 1)[1].split("{selected&&", 1)[0]
assert "Run market ingestion" not in option_block
assert "Ingestion scope" not in option_block
assert "Refresh before scan" not in option_block

# Daily Scanner operational controls remain available in its own conditional block.
assert "{!isOptionWorkspace&&<>" in pages
assert "Run market ingestion" in pages

print("Milestone 53 Phase 3 persisted-snapshot Option Scanner assertions passed.")
