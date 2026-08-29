from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import (
    Column,
    Date,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    text,
)

from trading_ai.scanner.options_market_data_ingestion import (
    CsvOptionHistoryProvider,
    IngestionManifestStore,
    OptionHistoryIngestionService,
)


def main() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    Table(
        "option_contract_history",
        metadata,
        Column("underlying_symbol", String, nullable=False),
        Column("expiry", Date, nullable=False),
        Column("quote_date", Date, nullable=False),
        Column("strike", Float, nullable=False),
        Column("option_type", String, nullable=False),
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
    )
    metadata.create_all(engine)

    with TemporaryDirectory() as directory:
        csv_path = Path(directory) / "options.csv"
        csv_path.write_text(
            "underlying_symbol,expiry,quote_date,strike,option_type,bid,ask,"
            "last,volume,open_interest,implied_volatility,delta,gamma,theta,vega\n"
            "AAPL,2026-08-21,2026-07-20,250,CALL,5.0,5.3,5.2,100,1000,"
            "0.35,0.45,0.02,-0.08,0.15\n"
            "AAPL,2026-08-21,2026-07-20,250,CALL,5.0,5.3,5.2,100,1000,"
            "0.35,0.45,0.02,-0.08,0.15\n",
            encoding="utf-8",
        )
        manifest = IngestionManifestStore(Path(directory) / "manifest.json")
        profile = OptionHistoryIngestionService(
            engine,
            CsvOptionHistoryProvider([csv_path]),
            manifest_store=manifest,
        ).run(batch_size=100)

        assert profile.input_records == 2
        assert profile.valid_records == 1
        assert profile.inserted_records == 1
        assert profile.skipped_records == 1

        with engine.connect() as connection:
            count = connection.execute(
                text("SELECT COUNT(*) FROM option_contract_history")
            ).scalar_one()
        assert count == 1

        resumed = OptionHistoryIngestionService(
            engine,
            CsvOptionHistoryProvider([csv_path]),
            manifest_store=manifest,
        ).run(batch_size=100)
        assert resumed.resumed_batches == 1
        assert resumed.input_records == 0

    print("Milestone 35 Phase 3 revised Step 2 ingestion assertions passed.")


if __name__ == "__main__":
    main()
