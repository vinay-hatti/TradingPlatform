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
            "volume": 800,
            "open_interest": 2500,
            "implied_volatility": 0.32,
            "delta": 0.55,
        },
        {
            "underlying_symbol": "AMZN",
            "expiry": "2026-08-21",
            "strike": 210,
            "option_type": "PUT",
            "bid": 4.0,
            "ask": 4.8,
            "volume": 150,
            "open_interest": 700,
            "implied_volatility": "35%",
            "delta": -0.42,
        },
    ]

    profile = OptionChainInspectionService().inspect(
        records,
        "AMZN",
        min_volume=100,
        min_open_interest=500,
        max_spread_pct=0.20,
    )
    assert profile.total_contracts == 2
    assert profile.filtered_contracts == 2
    assert len(profile.calls) == 1
    assert len(profile.puts) == 1
    assert profile.calls[0].liquidity_status == "HIGH"
    assert profile.puts[0].implied_volatility == 0.35

    print(
        "Milestone 35 Phase 5 Step 6 option-chain assertions passed."
    )


if __name__ == "__main__":
    main()
