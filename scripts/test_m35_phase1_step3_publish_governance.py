from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from trading_ai.scanner.universe_management import AutomaticUniverseBuilderService, ProviderFetchResult, SecurityProfile, UniverseRefreshPolicy

class SmallProvider:
    name="SMALL"
    def fetch(self):
        return ProviderFetchResult(self.name, (SecurityProfile(symbol="A", exchange="NASDAQ", asset_type="EQUITY", source=self.name),), datetime.now(timezone.utc))

def main():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        result=AutomaticUniverseBuilderService(UniverseRefreshPolicy(minimum_symbol_count=2)).refresh([SmallProvider()], output_dir=root/"data", report_dir=root/"reports")
        assert not result.published and result.status == "REJECTED"
        assert not (root/"data/us_listed_equities_etfs.csv").exists()
        assert (root/"reports/rejected_refresh_summary.json").exists()
    print("M35 Phase 1 Step 3 publication governance assertions passed.")
if __name__ == "__main__": main()
