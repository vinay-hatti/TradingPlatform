import csv
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.options_market_data_quality import (
    OptionContractIdentity,
    OptionContractValidationEngine,
    OptionQuoteRecord,
    OptionSide,
    write_option_validation_csv,
    write_option_validation_json,
)


def main() -> None:
    record = OptionQuoteRecord(
        identity=OptionContractIdentity(
            underlying_symbol="MSFT",
            expiration_date=date(2026, 8, 21),
            strike=500.0,
            option_side=OptionSide.PUT,
        ),
        quote_date=date(2026, 7, 20),
        bid=4.0,
        ask=4.5,
        delta=-0.35,
    )
    result = OptionContractValidationEngine().evaluate(record)

    with TemporaryDirectory() as directory:
        root = Path(directory)
        json_path = write_option_validation_json(
            [result],
            root / "validation.json",
        )
        csv_path = write_option_validation_csv(
            [result],
            root / "validation.csv",
        )

        payload = json.loads(json_path.read_text())
        assert payload["record_count"] == 1
        assert payload["valid_count"] == 1

        with csv_path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["underlying_symbol"] == "MSFT"
        assert rows[0]["valid"] == "True"

    print("Milestone 35 Phase 3 Step 1 option serialization assertions passed.")


if __name__ == "__main__":
    main()
