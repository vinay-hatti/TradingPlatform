from __future__ import annotations

from datetime import date

from sqlalchemy import Column, Date, Float, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import sessionmaker

from trading_ai.database.repositories.option_chain import OptionChainRepository
from trading_ai.research_workstation.scanner.options_data_adapter import (
    RepositoryOptionsDataAdapter,
)


def main() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    table = Table(
        "historical_option_quotes",
        metadata,
        Column("underlying", String),
        Column("as_of_date", Date),
        Column("expiration_date", Date),
        Column("strike", Float),
        Column("right", String),
        Column("bid", Float),
        Column("ask", Float),
        Column("last_price", Float),
        Column("volume", Integer),
        Column("oi", Integer),
        Column("iv", Float),
        Column("delta", Float),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            [
                {
                    "underlying": "AAA",
                    "as_of_date": date(2026, 7, 1),
                    "expiration_date": date(2026, 8, 21),
                    "strike": 100.0,
                    "right": "CALL",
                    "bid": 2.0,
                    "ask": 2.1,
                    "last_price": 2.05,
                    "volume": 125,
                    "oi": 700,
                    "iv": 0.31,
                    "delta": 0.51,
                }
            ],
        )

    Session = sessionmaker(bind=engine)
    with Session() as session:
        repository = OptionChainRepository(session)
        rows = repository.get_range(("AAA",))
        assert repository.resolved_table_name == "historical_option_quotes"
        assert len(rows) == 1
        assert rows[0]["symbol"] == "AAA"
        assert rows[0]["open_interest"] == 700
        assert rows[0]["implied_volatility"] == 0.31

    adapter = RepositoryOptionsDataAdapter(session_factory=Session)
    result = adapter.load_contracts(symbols=("AAA", "BBB"))
    assert adapter.last_resolved_table_name == "historical_option_quotes"
    assert len(result["AAA"]) == 1
    assert result["AAA"][0].open_interest == 700
    assert result["AAA"][0].option_type == "call"
    assert result["BBB"] == ()

    empty_engine = create_engine("sqlite+pysqlite:///:memory:")
    EmptySession = sessionmaker(bind=empty_engine)
    empty_adapter = RepositoryOptionsDataAdapter(session_factory=EmptySession)
    assert empty_adapter.load_contracts(symbols=("AAA",))["AAA"] == ()
    assert empty_adapter.last_resolved_table_name is None

    print("All Milestone 34 Phase 1 Step 3 repository-native assertions passed.")


if __name__ == "__main__":
    main()
