from datetime import date

from sqlalchemy import Column, Date, Float, MetaData, String, Table, create_engine

from trading_ai.scanner.market_data_quality import PriceHistoryCoverageRepository


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
    result = PriceHistoryCoverageRepository(engine).aggregate(["AAPL", "MSFT", "NVDA"])
    assert set(result) == {"AAPL", "MSFT"}
    assert result["AAPL"].row_count == 2
    assert result["AAPL"].trading_day_count == 2
    assert result["AAPL"].earliest_date == date(2026, 1, 2)
    assert result["AAPL"].latest_date == date(2026, 1, 5)
    print("Milestone 35 Phase 2 Step 2 coverage repository assertions passed.")


if __name__ == "__main__":
    main()
