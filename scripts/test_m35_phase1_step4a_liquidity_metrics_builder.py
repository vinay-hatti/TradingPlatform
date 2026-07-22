from __future__ import annotations

import csv
import tempfile
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import Column, Date, Float, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session

from trading_ai.scanner.universe_management.liquidity_metrics_builder import LiquidityMetricsBuildPolicy, LiquidityMetricsBuilder


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        engine = create_engine("sqlite://")
        metadata = MetaData()
        prices = Table("price_history", metadata, Column("symbol", String), Column("date", Date), Column("close", Float), Column("volume", Float))
        options = Table("option_contract_history", metadata, Column("underlying_symbol", String), Column("quote_date", Date), Column("bid", Float), Column("ask", Float), Column("volume", Float), Column("open_interest", Float))
        metadata.create_all(engine)
        today = date.today()
        with engine.begin() as connection:
            connection.execute(prices.insert(), [
                {"symbol": symbol, "date": today-timedelta(days=index), "close": base+index, "volume": volume}
                for symbol, base, volume in (("AAPL", 200, 1_000_000), ("MSFT", 400, 800_000)) for index in range(10)
            ])
            connection.execute(options.insert(), [
                {"underlying_symbol":"AAPL", "quote_date":today, "bid":2.0, "ask":2.2, "volume":100, "open_interest":500},
                {"underlying_symbol":"AAPL", "quote_date":today, "bid":3.0, "ask":3.3, "volume":200, "open_interest":700},
            ])
        universe = root / "universe.csv"
        universe.write_text("symbol,asset_type,exchange\nAAPL,EQUITY,NASDAQ\nMSFT,EQUITY,NASDAQ\n", encoding="utf-8")
        reference = root / "reference.csv"
        reference.write_text("symbol,market_cap,halted\nAAPL,3000000000000,false\nMSFT,2500000000000,false\n", encoding="utf-8")
        output = root / "liquidity_metrics.csv"
        with Session(engine) as session:
            result = LiquidityMetricsBuilder(LiquidityMetricsBuildPolicy(minimum_price_observations=5)).build(
                session=session, universe_csv=universe, reference_csv=reference,
                output_csv=output, manifest_json=root/"manifest.json", diagnostics_json=root/"diagnostics.json", as_of=today,
            )
        assert result.status == "READY"
        assert result.metrics_count == 2
        rows = list(csv.DictReader(output.open()))
        by_symbol = {row["symbol"]: row for row in rows}
        assert int(by_symbol["AAPL"]["option_volume"]) == 300
        assert int(by_symbol["AAPL"]["option_open_interest"]) == 1200
        assert by_symbol["MSFT"]["option_volume"] == ""
        assert float(by_symbol["AAPL"]["average_daily_dollar_volume"]) > 0
        print("M35 Phase 1 Step 4A liquidity metrics builder assertions passed.")


if __name__ == "__main__":
    main()
