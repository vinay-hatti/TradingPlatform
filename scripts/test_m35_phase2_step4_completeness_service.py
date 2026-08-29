from datetime import date

from sqlalchemy import Column, Date, MetaData, String, Table, create_engine

from trading_ai.scanner.market_data_quality.completeness import (
    MarketDataCompletenessPolicy,
    MarketDataCompletenessService,
)


def main() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    price_history = Table(
        "price_history",
        metadata,
        Column("symbol", String, nullable=False),
        Column("date", Date, nullable=False),
    )
    metadata.create_all(engine)

    rows = [
        {"symbol": "AAPL", "date": date(2026, 7, 14)},
        {"symbol": "AAPL", "date": date(2026, 7, 15)},
        {"symbol": "AAPL", "date": date(2026, 7, 16)},
        {"symbol": "AAPL", "date": date(2026, 7, 17)},
        {"symbol": "AAPL", "date": date(2026, 7, 20)},
        {"symbol": "MSFT", "date": date(2026, 7, 14)},
    ]
    with engine.begin() as connection:
        connection.execute(price_history.insert(), rows)

    service = MarketDataCompletenessService(
        engine,
        policy=MarketDataCompletenessPolicy(lookback_trading_days=5),
    )
    profile = service.evaluate(
        ["AAPL", "MSFT", "NVDA"],
        as_of_date=date(2026, 7, 20),
    )

    assert profile.canonical_symbol_count == 3
    assert profile.evaluated_symbol_count == 3
    assert len(profile.symbol_profiles) == 3
    aapl = next(item for item in profile.symbol_profiles if item.symbol == "AAPL")
    nvda = next(item for item in profile.symbol_profiles if item.symbol == "NVDA")
    assert aapl.continuity_percentage == 100.0
    assert nvda.observed_trading_days == 0
    assert profile.failed_symbol_count >= 1

    print("Milestone 35 Phase 2 Step 4 completeness service assertions passed.")


if __name__ == "__main__":
    main()
