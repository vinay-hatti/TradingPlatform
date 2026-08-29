from trading_ai.scanner.options_market_data_quality import (
    OptionQuoteNormalizer,
    OptionSide,
)


def main() -> None:
    normalizer = OptionQuoteNormalizer()
    record = normalizer.normalize(
        {
            "Ticker": "aapl",
            "Expiry": "2026-08-21",
            "Date": "2026-07-20",
            "Strike Price": "250",
            "Put Call": "C",
            "Bid Price": "5.10",
            "Ask Price": "5.40",
            "OpenInterest": "1000",
            "IV": "0.35",
            "Contract Symbol": "AAPL260821C00250000",
            "source": "test",
        }
    )

    assert record.identity.underlying_symbol == "AAPL"
    assert record.identity.option_side is OptionSide.CALL
    assert record.identity.strike == 250.0
    assert record.open_interest == 1000
    assert record.provider_symbol == "AAPL260821C00250000"
    assert record.metadata["source"] == "test"
    assert round(record.spread_percentage or 0.0, 6) == round(0.30 / 5.25, 6)

    print("Milestone 35 Phase 3 Step 1 option normalization assertions passed.")


if __name__ == "__main__":
    main()
