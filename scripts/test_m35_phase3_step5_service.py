import json
import tempfile
from datetime import date
from pathlib import Path

from trading_ai.scanner.options_market_data_readiness.service import (
    OptionDataReadinessService,
)


def main():
    coverage = {
        "as_of_date": "2026-07-20",
        "profiles": [
            {
                "symbol": "AAPL",
                "governance_status": "READY",
                "overall_coverage_score": 0.9,
                "contract_count": 100,
                "expiration_count": 3,
                "distinct_strike_count": 30,
                "governance_reasons": [],
            }
        ],
    }
    quality = {
        "as_of_date": "2026-07-20",
        "quote_data_observed": False,
        "profiles": [
            {
                "symbol": "AAPL",
                "governance_status": "READY",
                "overall_quality_score": 1.0,
                "governance_reasons": [],
                "informational_notes": [
                    "provider-aware quality score used"
                ],
            }
        ],
    }

    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        coverage_path = directory / "coverage.json"
        quality_path = directory / "quality.json"
        coverage_path.write_text(json.dumps(coverage))
        quality_path.write_text(json.dumps(quality))

        result = OptionDataReadinessService().run(
            as_of_date=date(2026, 7, 20),
            coverage_report_path=coverage_path,
            quality_report_path=quality_path,
        )

        assert result.symbols_evaluated == 1
        assert result.ready_symbols == 1
        assert result.profiles[0].symbol == "AAPL"

    print("Milestone 35 Phase 3 Step 5 service assertions passed.")


if __name__ == "__main__":
    main()
