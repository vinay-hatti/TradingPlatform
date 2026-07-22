import csv
import json
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from trading_ai.scanner.options_market_data_coverage.contracts import (
    GovernanceStatus,
    OptionChainCoverageProfile,
    OptionChainCoverageRunProfile,
)
from trading_ai.scanner.options_market_data_coverage.serialization import (
    write_json_atomic,
    write_symbol_csv,
)


def main():
    profile = OptionChainCoverageRunProfile(
        as_of_date=date(2026, 7, 20),
        generated_at=datetime.now(timezone.utc),
        source_table="option_contract_history",
        symbols_evaluated=1,
        ready_symbols=1,
        review_symbols=0,
        failed_symbols=0,
        average_coverage_score=1.0,
        minimum_coverage_score=1.0,
        maximum_coverage_score=1.0,
        profiles=(
            OptionChainCoverageProfile(
                symbol="AAPL",
                quote_date=date(2026, 7, 20),
                contract_count=20,
                call_count=10,
                put_count=10,
                expiration_count=2,
                distinct_strike_count=5,
                minimum_expiration=date(2026, 8, 21),
                maximum_expiration=date(2026, 9, 18),
                minimum_dte=32,
                maximum_dte=60,
                call_put_ratio=1.0,
                call_put_balance_score=1.0,
                expiration_coverage_score=1.0,
                strike_surface_score=1.0,
                overall_coverage_score=1.0,
                governance_status=GovernanceStatus.READY,
            ),
        ),
    )

    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        json_path = write_json_atomic(directory / "run.json", profile)
        csv_path = write_symbol_csv(directory / "symbols.csv", profile)

        payload = json.loads(json_path.read_text())
        assert payload["profiles"][0]["governance_status"] == "READY"

        with csv_path.open() as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["symbol"] == "AAPL"

    print("Milestone 35 Phase 3 Step 3 serialization assertions passed.")


if __name__ == "__main__":
    main()
