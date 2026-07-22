from datetime import date
from tempfile import TemporaryDirectory
from pathlib import Path
import json

from sqlalchemy import Column, Date, Float, MetaData, String, Table, create_engine

from trading_ai.scanner.market_data_quality import CoverageStatus, MarketDataCoveragePolicy, MarketDataCoverageService


class Symbols:
    def symbols(self):
        return ("AAPL", "MSFT", "NVDA")


def main():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    prices = Table(
        "price_history", metadata,
        Column("symbol", String, primary_key=True),
        Column("date", Date, primary_key=True),
        Column("close", Float),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(prices.insert(), [
            {"symbol": "AAPL", "date": date(2026, 1, 2), "close": 100.0},
            {"symbol": "AAPL", "date": date(2026, 1, 5), "close": 101.0},
            {"symbol": "MSFT", "date": date(2026, 1, 2), "close": 200.0},
        ])
    policy = MarketDataCoveragePolicy(
        minimum_history_days=2,
        ready_coverage_percentage=100,
        degraded_coverage_percentage=60,
        review_coverage_percentage=30,
        ready_minimum_history_percentage=100,
        degraded_minimum_history_percentage=30,
    )
    service = MarketDataCoverageService(engine, canonical_source=Symbols(), policy=policy)
    profile = service.evaluate()
    assert profile.canonical_symbol_count == 3
    assert profile.symbols_with_history == 2
    assert profile.symbols_without_history == 1
    assert profile.symbols_meeting_minimum_history == 1
    assert profile.status is CoverageStatus.DEGRADED
    assert profile.symbol_profiles[2].symbol == "NVDA"
    assert profile.symbol_profiles[2].status is CoverageStatus.FAILED

    with TemporaryDirectory() as directory:
        reported, paths = service.evaluate_and_write(directory)
        assert reported.canonical_symbol_count == 3
        assert paths.json_path.is_file()
        assert paths.symbol_csv_path.is_file()
        payload = json.loads(paths.json_path.read_text())
        assert payload["canonical_symbol_count"] == 3
        assert len(payload["symbol_profiles"]) == 3
        assert Path(paths.symbol_csv_path).read_text().count("\n") == 4
    print("Milestone 35 Phase 2 Step 2 coverage service assertions passed.")


if __name__ == "__main__":
    main()
