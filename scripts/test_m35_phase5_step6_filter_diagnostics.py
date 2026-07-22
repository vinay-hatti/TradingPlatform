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
            "bid": 5.0,
            "ask": 5.4,
            "volume": 10,
            "open_interest": 2500,
        },
        {
            "underlying_symbol": "AMZN",
            "expiry": "2026-08-21",
            "strike": 225,
            "option_type": "CALL",
            "bid": "",
            "ask": "",
            "volume": 800,
            "open_interest": 2500,
        },
        {
            "underlying_symbol": "AMZN",
            "expiry": "2026-08-21",
            "strike": 230,
            "option_type": "CALL",
            "bid": 1.0,
            "ask": 2.0,
            "volume": 800,
            "open_interest": 2500,
        },
    ]

    profile = OptionChainInspectionService().inspect(
        records,
        "AMZN",
        min_volume=100,
        min_open_interest=500,
        max_spread_pct=0.20,
    )

    assert profile.filtered_contracts == 0
    assert profile.rejection_counts["volume_below_minimum"] == 1
    assert profile.rejection_counts["missing_or_invalid_bid_ask"] == 1
    assert profile.rejection_counts["spread_above_maximum"] == 1
    assert profile.field_coverage["volume_present"] == 3
    assert profile.observed_ranges["volume"]["max"] == 800.0

    print(
        "Milestone 35 Phase 5 Step 6 filter-diagnostic assertions passed."
    )


if __name__ == "__main__":
    main()
