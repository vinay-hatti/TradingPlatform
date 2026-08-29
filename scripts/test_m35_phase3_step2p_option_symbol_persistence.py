from datetime import date
from pathlib import Path
import sys

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


def make_record(option_symbol: str | None) -> OptionQuoteRecord:
    return OptionQuoteRecord(
        identity=OptionContractIdentity(
            underlying_symbol="A",
            expiration_date=date(2026, 8, 21),
            strike=120.0,
            option_side=OptionSide.PUT,
        ),
        quote_date=date(2026, 7, 20),
        bid=None,
        ask=None,
        last=0.0,
        volume=133,
        open_interest=109,
        implied_volatility=0.3489,
        delta=-0.1917,
        gamma=0.0206,
        theta=-0.0565,
        vega=0.0959,
        provider_symbol=option_symbol,
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
        Column("bid", Float),
        Column("ask", Float),
        Column("last", Float),
        Column("volume", Integer),
        Column("open_interest", Integer),
        Column("implied_volatility", Float),
        Column("delta", Float),
        Column("gamma", Float),
        Column("theta", Float),
        Column("vega", Float),
        UniqueConstraint(
            "option_symbol",
            "quote_date",
            name="uq_option_symbol_quote_date",
        ),
    )
    metadata.create_all(engine)

    writer = OptionHistoryWriter(engine)

    result = writer.write([make_record("O:A260821P00120000")])
    assert result.inserted_records == 1

    generated = writer.write([make_record(None)])
    assert generated.updated_records == 1

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT option_symbol, underlying_symbol, quote_date
                FROM option_contract_history
                """
            )
        ).mappings().one()

    assert row["option_symbol"] == "O:A260821P00120000"
    assert row["underlying_symbol"] == "A"

    print(
        "Milestone 35 Phase 3 option_symbol persistence assertions passed."
    )


if __name__ == "__main__":
    main()
