import json, tempfile
from datetime import date
from pathlib import Path
from trading_ai.scanner.cross_asset_data_foundation.contracts import AssetClass, CrossAssetFeatureProfile, CrossAssetGovernanceStatus
from trading_ai.scanner.cross_asset_data_foundation.serialization import write_jsonl_atomic

def main():
    r = CrossAssetFeatureProfile(
        "SPY", AssetClass.EQUITY_INDEX, "US_LARGE_CAP", None, date(2026,7,20),
        100, 600.0, 50_000_000, .01, .02, .03, .15, 5.0, .008,
        595.0, 580.0, "UP", .025, "LOW", None, None, 1.1, "DEEP",
        CrossAssetGovernanceStatus.READY, ())
    with tempfile.TemporaryDirectory() as d:
        p = write_jsonl_atomic(Path(d)/"f.jsonl", [r])
        x = json.loads(p.read_text())
        assert x["symbol"] == "SPY" and x["governance_status"] == "READY"
    print("Milestone 35 Phase 5 Step 1 serialization assertions passed.")

if __name__ == "__main__":
    main()
