from trading_ai.scanner.dashboard.option_chain_service import (
    OptionChainInspectionService,
)


def main() -> None:
    records = [
        {
            "underlying_symbol": "AMZN",
            "expiry": "2026-08-21",
            "strike": 220,
            "option_type": "CALL",
            "last": 5.2,
            "volume": 800,
            "open_interest": 2500,
        },
        {
            "underlying_symbol": "AMZN",
            "expiry": "2026-08-21",
            "strike": 225,
            "option_type": "CALL",
            "last": 3.8,
            "volume": 200,
            "open_interest": 100,
        },
    ]

    service = OptionChainInspectionService()

    strict = service.inspect(
        records,
        "AMZN",
        min_volume=100,
        min_open_interest=500,
        max_spread_pct=0.20,
    )
    assert strict.filtered_contracts == 0
    assert strict.rejection_counts["missing_or_invalid_bid_ask"] == 1

    historical = service.inspect(
        records,
        "AMZN",
        min_volume=100,
        min_open_interest=500,
        max_spread_pct=0.20,
        quote_policy=service.HISTORICAL_ALLOW_MISSING_QUOTES,
    )
    assert historical.filtered_contracts == 1
    assert historical.calls[0].liquidity_status == "HISTORICAL_NO_QUOTE"
    assert "HISTORICAL_QUOTES_UNAVAILABLE" in historical.calls[0].warnings
    assert "HISTORICAL_DATA_WITHOUT_BID_ASK_QUOTES" in historical.warnings

    print(
        "Milestone 35 Phase 5 Step 6 historical quote-policy assertions passed."
    )


if __name__ == "__main__":
    main()
