from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "trading_ai" / "scanner" / "options_market_data_ingestion" / "manifest.py"
spec = importlib.util.spec_from_file_location("manifest_m52_phase36", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
IngestionManifestStore = module.IngestionManifestStore

with tempfile.TemporaryDirectory() as td:
    store = IngestionManifestStore(Path(td) / "manifest.json")
    store.begin_cycle("cycle-1", metadata={"mode": "FRESH"})
    store.mark_completed("stable-batch", cycle_id="cycle-1")
    assert store.is_completed("stable-batch", cycle_id="cycle-1")
    store.complete_cycle("cycle-1", metadata={"completed_successfully": True})
    store.begin_cycle("cycle-2", metadata={"mode": "FRESH"})
    assert not store.is_completed("stable-batch", cycle_id="cycle-2")
    assert store.is_completed("stable-batch", cycle_id="cycle-1")
    latest = store.latest_cycle()
    assert latest and latest["cycle_id"] == "cycle-2"
print("Milestone 52 Phase 3.6 manifest-cycle assertions passed.")
