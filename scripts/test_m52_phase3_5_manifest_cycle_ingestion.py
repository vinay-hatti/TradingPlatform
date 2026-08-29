from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import Column, Date, Float, Integer, MetaData, String, Table, create_engine

from trading_ai.scanner.options_market_data_ingestion import (
    CsvOptionHistoryProvider,
    IngestionManifestStore,
    OptionHistoryIngestionService,
)


def main() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    Table(
        "option_contract_history", metadata,
        Column("underlying_symbol", String, nullable=False),
        Column("option_symbol", String, nullable=False),
        Column("quote_date", Date, nullable=False),
        Column("expiry", Date, nullable=False),
        Column("option_type", String, nullable=False),
        Column("strike", Float, nullable=False),
        Column("bid", Float), Column("ask", Float), Column("last", Float),
        Column("volume", Integer), Column("open_interest", Integer),
        Column("implied_volatility", Float), Column("delta", Float),
        Column("gamma", Float), Column("theta", Float), Column("vega", Float),
    )
    metadata.create_all(engine)
    with TemporaryDirectory() as directory:
        root = Path(directory)
        csv_path = root / "options.csv"
        csv_path.write_text(
            "underlying_symbol,option_symbol,expiry,quote_date,strike,option_type,bid,ask,last,volume,open_interest,implied_volatility,delta,gamma,theta,vega\n"
            "AAPL,O:AAPL260821C00250000,2026-08-21,2026-07-27,250,CALL,5.0,5.2,5.1,100,1000,0.35,0.45,0.02,-0.08,0.15\n",
            encoding="utf-8",
        )
        manifest = IngestionManifestStore(root / "manifest.json")
        provider = CsvOptionHistoryProvider([csv_path])
        first = OptionHistoryIngestionService(engine, provider, manifest_store=manifest).run(
            batch_size=100, manifest_cycle_id="cycle-1"
        )
        assert first.valid_records == 1 and first.resumed_batches == 0
        same_cycle = OptionHistoryIngestionService(engine, provider, manifest_store=manifest).run(
            batch_size=100, manifest_cycle_id="cycle-1"
        )
        assert same_cycle.valid_records == 0 and same_cycle.resumed_batches == 1
        next_cycle = OptionHistoryIngestionService(engine, provider, manifest_store=manifest).run(
            batch_size=100, manifest_cycle_id="cycle-2"
        )
        assert next_cycle.valid_records == 1 and next_cycle.resumed_batches == 0
    print("Milestone 52 Phase 3.5 manifest-cycle ingestion assertions passed.")


if __name__ == "__main__":
    main()
