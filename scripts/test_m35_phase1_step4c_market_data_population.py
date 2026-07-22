from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
import tempfile

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trading_ai.database.base import Base
from trading_ai.market.models import PriceHistory
from trading_ai.scanner.market_data_population import (
    BulkMarketDataPopulationService, MarketDataPopulationPolicy, PriceBar,
)


class FakeProvider:
    name = "FAKE"
    def fetch_batch(self, symbols, start, end):
        output = {}
        for symbol in symbols:
            output[symbol] = tuple(
                PriceBar(symbol, date(2026, 6, 1) + timedelta(days=i), 10+i, 11+i, 9+i, 10.5+i, 100000+i)
                for i in range(25)
            )
        return output


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        universe = root / "universe.csv"
        with universe.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["symbol"]); writer.writeheader()
            writer.writerows([{"symbol": "AAA"}, {"symbol": "BBB"}, {"symbol": "CCC"}])
        engine = create_engine(f"sqlite:///{root/'test.db'}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        policy = MarketDataPopulationPolicy(
            lookback_days=90, minimum_bars=20, stale_after_days=3650,
            minimum_coverage_pct=100.0, batch_size=2, max_retries=0,
            request_pause_seconds=0, retry_backoff_seconds=0,
        )
        result = BulkMarketDataPopulationService(FakeProvider(), policy).run(
            session=session, universe_csv=universe, report_dir=root / "reports",
            end=date(2026, 7, 1),
        )
        assert result.status == "READY", result
        assert result.succeeded_symbols == 3
        assert result.rows_upserted == 75
        assert result.coverage.covered_symbols == 3
        assert len(session.scalars(select(PriceHistory)).all()) == 75
        second = BulkMarketDataPopulationService(FakeProvider(), policy).run(
            session=session, universe_csv=universe, report_dir=root / "reports2",
            end=date(2026, 7, 1),
        )
        assert second.skipped_fresh_symbols == 3
        assert second.attempted_symbols == 0
        assert (root / "reports" / "population_summary.json").is_file()
        assert (root / "reports" / "coverage_report.json").is_file()
        assert (root / "reports" / "population_manifest.json").is_file()
        session.close()
    print("M35 Phase 1 Step 4C market-data population assertions passed.")


if __name__ == "__main__":
    main()
