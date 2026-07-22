from datetime import date

from sqlalchemy import (
    Column,
    Date,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    text,
)

from trading_ai.scanner.options_market_data_ingestion.persistence import (
    OptionHistoryWriter,
)
from trading_ai.scanner.options_market_data_quality.contracts import (
    OptionContractIdentity,
    OptionQuoteRecord,
    OptionSide,
)


def make_record(symbol: str, **overrides):
    values = {
        "bid": 1.4,
        "ask": 1.6,
        "last": 1.5,
        "volume": 133,
        "open_interest": 109,
        "implied_volatility": 0.349,
        "delta": -0.19,
        "gamma": 0.02,
        "theta": -0.05,
        "vega": 0.09,
    }
    values.update(overrides)

    return OptionQuoteRecord(
        identity=OptionContractIdentity(
            underlying_symbol="A",
            expiration_date=date(2026, 8, 21),
            strike=float(symbol[-3:]),
            option_side=OptionSide.PUT,
        ),
        quote_date=date(2026, 7, 20),
        provider_symbol=f"O:A260821P{symbol}",
        **values,
    )


def main():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()

    Table(
        "option_contract_history",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("underlying_symbol", String, nullable=False),
        Column("option_symbol", String, nullable=False),
        Column("quote_date", Date, nullable=False),
        Column("expiry", Date, nullable=False),
        Column("option_type", String, nullable=False),
        Column("strike", Float, nullable=False),
        Column("bid", Float, nullable=False),
        Column("ask", Float, nullable=False),
        Column("last", Float, nullable=False),
        Column("volume", Integer, nullable=False),
        Column("open_interest", Integer, nullable=False),
        Column("implied_volatility", Float, nullable=False),
        Column("delta", Float, nullable=False),
        Column("gamma", Float, nullable=False),
        Column("theta", Float, nullable=False),
        Column("vega", Float, nullable=False),
        UniqueConstraint(
            "underlying_symbol",
            "expiry",
            "quote_date",
            "strike",
            "option_type",
            name="uq_complete_snapshot",
        ),
    )
    metadata.create_all(engine)

    records = [
        make_record("120", bid=None),
        make_record("121", ask=None),
        make_record("122", last=None),
        make_record("123", volume=None),
        make_record("124", open_interest=None),
        make_record("125", implied_volatility=None),
        make_record("126", delta=None),
        make_record("127", gamma=None),
        make_record("128", theta=None),
        make_record("129", vega=None),
        make_record("130"),
    ]

    result = OptionHistoryWriter(engine).write(records)

    assert result.inserted_records == 1
    assert result.skipped_records == 10

    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM option_contract_history")
        ).scalar_one()

    assert count == 1
    print(
        "Milestone 35 Phase 3 all-null completeness assertions passed."
    )


if __name__ == "__main__":
    main()
