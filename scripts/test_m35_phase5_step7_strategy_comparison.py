from trading_ai.scanner.dashboard.strategy_comparison_service import (
    StrategyComparisonService,
)


def main() -> None:
    payload = {
        "symbol": "AMZN",
        "quote_policy": "STRICT",
        "calls": [
            {
                "symbol": "AMZN",
                "expiry": "2026-08-21",
                "strike": 215,
                "option_type": "CALL",
                "bid": 8.0,
                "ask": 8.4,
                "last": 8.2,
                "volume": 900,
                "open_interest": 3000,
                "delta": 0.62,
            },
            {
                "symbol": "AMZN",
                "expiry": "2026-08-21",
                "strike": 220,
                "option_type": "CALL",
                "bid": 5.0,
                "ask": 5.4,
                "last": 5.2,
                "volume": 800,
                "open_interest": 2500,
                "delta": 0.54,
            },
        ],
        "puts": [],
    }

    profile = StrategyComparisonService().compare(
        payload,
        direction="CALL",
        max_candidates=10,
    )
    assert profile.symbol == "AMZN"
    assert profile.source_contracts == 2
    assert profile.generated_strategies == 3
    assert len(profile.ranked_strategies) == 3
    assert any(
        item.strategy_type == "BULL_CALL_SPREAD"
        for item in profile.ranked_strategies
    )

    print(
        "Milestone 35 Phase 5 Step 7 strategy-comparison assertions passed."
    )


if __name__ == "__main__":
    main()
