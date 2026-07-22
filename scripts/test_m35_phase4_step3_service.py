import json
import tempfile
from datetime import date
from pathlib import Path

from trading_ai.scanner.option_surface_persistence.contracts import (
    SurfacePersistencePolicy,
)
from trading_ai.scanner.option_surface_persistence.service import (
    OptionSurfacePersistenceService,
)


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        expiration_input = root / "expiration.jsonl"
        symbol_input = root / "symbol.jsonl"

        write_jsonl(
            expiration_input,
            [
                {
                    "underlying_symbol": "AAPL",
                    "quote_date": "2026-07-20",
                    "expiry": "2026-08-21",
                    "days_to_expiration": 32,
                    "contract_count": 20,
                    "call_contract_count": 10,
                    "put_contract_count": 10,
                    "strike_count": 10,
                    "total_volume": 500,
                    "total_open_interest": 5000,
                    "governance_status": "READY",
                    "governance_reasons": [],
                },
                {
                    "underlying_symbol": "MSFT",
                    "quote_date": "2026-07-20",
                    "expiry": "2026-08-21",
                    "days_to_expiration": 32,
                    "contract_count": 8,
                    "call_contract_count": 4,
                    "put_contract_count": 4,
                    "strike_count": 4,
                    "total_volume": 100,
                    "total_open_interest": 400,
                    "governance_status": "EXCLUDED",
                    "governance_reasons": ["insufficient coverage"],
                },
            ],
        )

        write_jsonl(
            symbol_input,
            [
                {
                    "underlying_symbol": "AAPL",
                    "quote_date": "2026-07-20",
                    "expiration_count": 2,
                    "ready_expiration_count": 2,
                    "review_expiration_count": 0,
                    "excluded_expiration_count": 0,
                    "total_contract_count": 40,
                    "total_volume": 1000,
                    "total_open_interest": 10000,
                    "governance_status": "READY",
                    "governance_reasons": [],
                }
            ],
        )

        profile = OptionSurfacePersistenceService(
            SurfacePersistencePolicy(
                allowed_expiration_statuses=("READY",),
                allowed_symbol_statuses=("READY",),
            )
        ).run(
            as_of_date=date(2026, 7, 20),
            expiration_input_path=expiration_input,
            symbol_input_path=symbol_input,
            expiration_csv_path=root / "expiration.csv",
            symbol_csv_path=root / "symbol.csv",
            governance_summary_path=root / "summary.json",
        )

        assert profile.expiration_records_read == 2
        assert profile.expiration_records_persisted == 1
        assert profile.expiration_records_filtered == 1
        assert profile.symbol_records_read == 1
        assert profile.symbol_records_persisted == 1
        assert profile.duplicate_expiration_keys == 0
        assert profile.duplicate_symbol_keys == 0
        assert (root / "expiration.csv").exists()
        assert (root / "symbol.csv").exists()
        assert (root / "summary.json").exists()

    print("Milestone 35 Phase 4 Step 3 service assertions passed.")


if __name__ == "__main__":
    main()
