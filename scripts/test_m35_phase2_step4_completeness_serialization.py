import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.market_data_quality.completeness import (
    MarketDataCompletenessEngine,
    MarketDataCompletenessPolicy,
)
from trading_ai.scanner.market_data_quality.completeness_serialization import (
    write_completeness_csv,
    write_completeness_json,
)


def main() -> None:
    engine = MarketDataCompletenessEngine(
        MarketDataCompletenessPolicy(lookback_trading_days=3)
    )
    symbol_profile = engine.evaluate_symbol(
        "AAPL",
        [date(2026, 7, 16), date(2026, 7, 17), date(2026, 7, 20)],
        as_of_date=date(2026, 7, 20),
    )
    profile = engine.evaluate_universe(
        [symbol_profile],
        canonical_symbol_count=1,
        as_of_date=date(2026, 7, 20),
    )

    with TemporaryDirectory() as directory:
        root = Path(directory)
        json_path = write_completeness_json(profile, root / "report.json")
        csv_path = write_completeness_csv(profile, root / "detail.csv")
        data = json.loads(json_path.read_text())
        assert data["canonical_symbol_count"] == 1
        assert data["symbol_profiles"][0]["symbol"] == "AAPL"
        assert "continuity_percentage" in csv_path.read_text()

    print("Milestone 35 Phase 2 Step 4 completeness serialization assertions passed.")


if __name__ == "__main__":
    main()
