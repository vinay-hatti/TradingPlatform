from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.options_market_data_ingestion import (
    CsvOptionHistoryProvider,
)


def main() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "options.csv"
        path.write_text(
            "underlying_symbol,expiry,quote_date,strike,option_type,bid,ask,"
            "last,volume,open_interest,implied_volatility,delta,gamma,theta,vega\n"
            "AAPL,2026-08-21,2026-07-20,250,CALL,5.0,5.3,5.2,100,1000,"
            "0.35,0.45,0.02,-0.08,0.15\n",
            encoding="utf-8",
        )

        batches = list(
            CsvOptionHistoryProvider([path]).iter_batches(batch_size=100)
        )
        assert len(batches) == 1
        assert len(batches[0].records) == 1
        assert batches[0].records[0].identity.underlying_symbol == "AAPL"

    print("Milestone 35 Phase 3 revised Step 2 CSV provider assertions passed.")


if __name__ == "__main__":
    main()
