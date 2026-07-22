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


def record(*, bid, ask, symbol):
    return OptionQuoteRecord(
        identity=OptionContractIdentity(
            underlying_symbol="A",
            expiration_date=date(2026, 8, 21),
            strike=120.0 if symbol.endswith("000") else 125.0,
            option_side=OptionSide.PUT,
        ),
        quote_date=date(2026, 7, 20),
        bid=bid,
        ask=ask,
        last=1.5,
        volume=133,
        open_interest=109,
        implied_volatility=0.3489,
        delta=-0.1917,
        gamma=0.0206,
        theta=-0.0565,
        vega=0.0959,
        provider_symbol=symbol,
    )


def main() -> None:
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
        Column("implied_volatility", Float),
        Column("delta", Float),
        Column("gamma", Float),
        Column("theta", Float),
        Column("vega", Float),
        UniqueConstraint(
            "underlying_symbol",
            "expiry",
            "quote_date",
            "strike",
            "option_type",
            name="uq_canonical_option_quote",
        ),
    )
    metadata.create_all(engine)

    writer = OptionHistoryWriter(engine)
    result = writer.write(
        [
            record(bid=None, ask=None, symbol="O:A260821P00120000"),
            record(bid=1.4, ask=1.6, symbol="O:A260821P00125001"),
        ]
    )

    assert result.inserted_records == 1
    assert result.skipped_records == 1

    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM option_contract_history")
        ).scalar_one()
        bid = connection.execute(
            text("SELECT bid FROM option_contract_history")
        ).scalar_one()

    assert count == 1
    assert bid == 1.4
    print(
        "Milestone 35 Phase 3 required-null filtering assertions passed."
    )


if __name__ == "__main__":
    main()
