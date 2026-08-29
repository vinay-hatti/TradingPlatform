import json
import tempfile
from datetime import date
from pathlib import Path

from trading_ai.scanner.option_surface_persistence.service import (
    OptionSurfacePersistenceService,
)


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        expiration_input = root / "expiration.jsonl"
        symbol_input = root / "symbol.jsonl"

        expiration = {
            "underlying_symbol": "AAPL",
            "quote_date": "2026-07-20",
            "expiry": "2026-08-21",
            "governance_status": "READY",
        }
        with expiration_input.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(expiration) + "\n")
            handle.write(json.dumps(expiration) + "\n")

        symbol = {
            "underlying_symbol": "AAPL",
            "quote_date": "2026-07-20",
            "governance_status": "READY",
        }
        with symbol_input.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(symbol) + "\n")

        try:
            OptionSurfacePersistenceService().run(
                as_of_date=date(2026, 7, 20),
                expiration_input_path=expiration_input,
                symbol_input_path=symbol_input,
                expiration_csv_path=root / "expiration.csv",
                symbol_csv_path=root / "symbol.csv",
                governance_summary_path=root / "summary.json",
            )
        except ValueError as exc:
            assert "duplicate expiration surface keys" in str(exc)
        else:
            raise AssertionError("duplicate key validation did not fail")

    print(
        "Milestone 35 Phase 4 Step 3 duplicate-governance "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
