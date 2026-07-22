from trading_ai.scanner.dashboard.filter_contracts import ScannerFilter
from trading_ai.scanner.dashboard.filter_service import ScannerFilterService


def main() -> None:
    records = [
        {
            "symbol": "AMZN",
            "institutional_score": 91,
            "probability_of_profit": 0.72,
            "liquidity_score": 88,
            "open_interest": 2500,
            "volume": 900,
            "spread_pct": 0.06,
            "sector": "Consumer Discretionary",
            "direction": "CALL",
            "strategy_type": "BULL_CALL_SPREAD",
        },
        {
            "symbol": "LLY",
            "institutional_score": 84,
            "probability_of_profit": 0.64,
            "liquidity_score": 92,
            "open_interest": 1800,
            "volume": 700,
            "spread_pct": 0.08,
            "sector": "Health Care",
            "direction": "PUT",
            "strategy_type": "BEAR_PUT_SPREAD",
        },
        {
            "symbol": "TSLA",
            "institutional_score": 61,
            "probability_of_profit": 0.53,
            "liquidity_score": 50,
            "open_interest": 300,
            "volume": 100,
            "spread_pct": 0.24,
            "sector": "Consumer Discretionary",
            "direction": "CALL",
            "strategy_type": "LONG_CALL",
        },
    ]

    filters = ScannerFilter(
        min_institutional_score=80,
        min_probability_of_profit=0.60,
        min_open_interest=1000,
        max_spread_pct=0.10,
        directions=("CALL",),
    )
    filtered = ScannerFilterService().apply(records, filters)

    assert len(filtered) == 1
    assert filtered[0]["symbol"] == "AMZN"

    percentage_filters = ScannerFilter(
        min_probability_of_profit=0.70,
        max_spread_pct=0.10,
    )
    percentage_records = [
        {
            "symbol": "AVGO",
            "probability_of_profit": "74%",
            "spread_pct": "8%",
        }
    ]
    result = ScannerFilterService().apply(
        percentage_records,
        percentage_filters,
    )
    assert len(result) == 1

    print(
        "Milestone 35 Phase 5 Step 4 scanner-filter assertions passed."
    )


if __name__ == "__main__":
    main()
