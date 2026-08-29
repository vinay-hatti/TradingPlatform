from trading_ai.scanner.dashboard.strategy_comparison_service import (
    StrategyComparisonService,
)


def main() -> None:
    payload = {
        "symbol": "AMZN",
        "quote_policy": "HISTORICAL_ALLOW_MISSING_QUOTES",
        "calls": [
            {
                "symbol": "AMZN",
                "expiry": "2026-08-21",
                "strike": 215,
                "option_type": "CALL",
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
    assert "HISTORICAL_QUOTE_POLICY_ACTIVE" in profile.warnings
    assert any(
        item.quote_quality == "HISTORICAL_LAST_ONLY"
        for item in profile.ranked_strategies
    )
    assert any(
        "INCOMPLETE" in warning
        for item in profile.ranked_strategies
        for warning in item.warnings
    )

    print(
        "Milestone 35 Phase 5 Step 7 historical-quote assertions passed."
    )


if __name__ == "__main__":
    main()
