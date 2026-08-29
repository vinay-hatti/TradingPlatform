import csv
import json
from datetime import date
from tempfile import TemporaryDirectory
from pathlib import Path

from trading_ai.scanner.market_data_quality import (
    CoverageStatus,
    MarketDataCoveragePolicy,
    coverage_profile_to_dict,
    write_coverage_json,
    write_symbol_coverage_csv,
)


def main() -> None:
    policy = MarketDataCoveragePolicy(minimum_history_days=2)
    item = policy.build_symbol_profile(
        symbol="AAPL",
        row_count=2,
        trading_day_count=2,
        earliest_date=date(2026, 7, 16),
        latest_date=date(2026, 7, 17),
    )
    profile = policy.evaluate((item,))
    assert profile.status is CoverageStatus.READY

    payload = coverage_profile_to_dict(profile)
    assert payload["status"] == "READY"
    assert payload["symbol_profiles"][0]["earliest_date"] == "2026-07-16"

    with TemporaryDirectory() as directory:
        root = Path(directory)
        json_path = write_coverage_json(profile, root / "coverage.json")
        csv_path = write_symbol_coverage_csv(profile, root / "symbols.csv")

        data = json.loads(json_path.read_text())
        assert data["canonical_symbol_count"] == 1
        assert data["symbol_profiles"][0]["symbol"] == "AAPL"

        with csv_path.open() as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["status"] == "READY"
        assert rows[0]["meets_minimum_history"] == "True"

    print("Milestone 35 Phase 2 Step 1 coverage serialization assertions passed.")


if __name__ == "__main__":
    main()
