import csv
import json
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from trading_ai.scanner.options_market_data_quality_analytics.contracts import (
    GovernanceStatus,
    OptionChainQualityProfile,
    OptionChainQualityRunProfile,
)
from trading_ai.scanner.options_market_data_quality_analytics.serialization import (
    write_json_atomic,
    write_symbol_csv,
)


def main():
    item = OptionChainQualityProfile(
        symbol="AAPL",
        quote_date=date(2026, 7, 20),
        contract_count=20,
        quoted_contracts=20,
        traded_contracts=20,
        liquid_contracts=20,
        valid_spread_contracts=20,
        crossed_market_contracts=0,
        locked_market_contracts=0,
        negative_market_value_contracts=0,
        iv_available_contracts=20,
        delta_available_contracts=20,
        full_greeks_contracts=20,
        quote_completeness_score=1.0,
        trade_completeness_score=1.0,
        liquidity_score=1.0,
        spread_integrity_score=1.0,
        iv_completeness_score=1.0,
        greeks_completeness_score=1.0,
        overall_quality_score=1.0,
        average_spread_pct=0.10,
        median_spread_pct=0.10,
        maximum_spread_pct=0.10,
        governance_status=GovernanceStatus.READY,
    )

    run = OptionChainQualityRunProfile(
        as_of_date=date(2026, 7, 20),
        generated_at=datetime.now(timezone.utc),
        source_table="option_contract_history",
        symbols_evaluated=1,
        ready_symbols=1,
        review_symbols=0,
        failed_symbols=0,
        average_quality_score=1.0,
        minimum_quality_score=1.0,
        maximum_quality_score=1.0,
        profiles=(item,),
    )

    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        json_path = write_json_atomic(directory / "run.json", run)
        csv_path = write_symbol_csv(directory / "profiles.csv", run)

        payload = json.loads(json_path.read_text())
        assert payload["profiles"][0]["governance_status"] == "READY"

        with csv_path.open() as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["symbol"] == "AAPL"

    print("Milestone 35 Phase 3 Step 4 serialization assertions passed.")


if __name__ == "__main__":
    main()
