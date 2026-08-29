import csv
import json
import tempfile
from datetime import date
from pathlib import Path

from trading_ai.scanner.option_surface_decision_integration.contracts import (
    SurfaceDecisionPolicy,
)
from trading_ai.scanner.option_surface_decision_integration.service import (
    OptionSurfaceDecisionIntegrationService,
)


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "symbols.csv"
        output = root / "features.jsonl"

        fields = [
            "underlying_symbol",
            "quote_date",
            "governance_status",
            "expiration_count",
            "total_contract_count",
            "total_volume",
            "total_open_interest",
            "nearest_atm_implied_volatility",
            "farthest_atm_implied_volatility",
            "atm_term_structure_slope",
            "aggregate_put_call_volume_ratio",
            "aggregate_put_call_open_interest_ratio",
        ]
        with source.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(
                {
                    "underlying_symbol": "AAPL",
                    "quote_date": "2026-07-20",
                    "governance_status": "READY",
                    "expiration_count": 3,
                    "total_contract_count": 100,
                    "total_volume": 400,
                    "total_open_interest": 15000,
                    "nearest_atm_implied_volatility": 0.25,
                    "farthest_atm_implied_volatility": 0.27,
                    "atm_term_structure_slope": 0.0004,
                    "aggregate_put_call_volume_ratio": 0.75,
                    "aggregate_put_call_open_interest_ratio": 0.85,
                }
            )

        profile = OptionSurfaceDecisionIntegrationService(
            SurfaceDecisionPolicy(
                minimum_total_open_interest=1000,
                minimum_total_volume=10,
            )
        ).run(
            as_of_date=date(2026, 7, 20),
            symbol_surface_csv_path=source,
            output_path=output,
        )

        assert profile.records_read == 1
        assert profile.records_generated == 1
        assert profile.eligible_count == 1
        assert output.exists()

        rows = [
            json.loads(line)
            for line in output.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rows[0]["underlying_symbol"] == "AAPL"
        assert rows[0]["feature_version"] == "m35.phase4.step4.v1"

    print("Milestone 35 Phase 4 Step 4 service assertions passed.")


if __name__ == "__main__":
    main()
