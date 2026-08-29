from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from trading_ai.scanner.universe_management import AutomaticUniverseBuilderService, ProviderFetchResult, SecurityProfile, UniverseRefreshPolicy


class Provider:
    name = "TEST"
    def fetch(self):
        rows = tuple(SecurityProfile(symbol=f"T{i:04d}", name=f"Test {i}", exchange="NASDAQ", asset_type="EQUITY", source=self.name) for i in range(25))
        return ProviderFetchResult(self.name, rows, datetime.now(timezone.utc))


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        service = AutomaticUniverseBuilderService(UniverseRefreshPolicy(minimum_symbol_count=20))
        first = service.refresh([Provider()], output_dir=root / "data", report_dir=root / "reports")
        assert first.published and first.symbol_count == 25 and first.added_count == 25
        second = service.refresh([Provider()], output_dir=root / "data", report_dir=root / "reports")
        assert second.published and second.unchanged_count == 25 and second.added_count == 0
        assert (root / "data/us_listed_equities_etfs.csv").is_file()
        assert (root / "data/universe_manifest.json").is_file()
        assert (root / "reports/universe_refresh_report.html").is_file()
    print("M35 Phase 1 Step 3 universe builder assertions passed.")


if __name__ == "__main__": main()
