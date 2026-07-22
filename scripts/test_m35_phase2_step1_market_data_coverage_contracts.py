from datetime import date

from trading_ai.scanner.market_data_quality import (
    CoverageStatus,
    MarketDataCoveragePolicy,
    SymbolCoverageProfile,
    UniverseCoverageProfile,
)


def main() -> None:
    policy = MarketDataCoveragePolicy(minimum_history_days=252)
    ready = policy.build_symbol_profile(
        symbol="aapl",
        row_count=300,
        trading_day_count=300,
        earliest_date=date(2025, 1, 2),
        latest_date=date(2026, 3, 15),
    )
    short = policy.build_symbol_profile(
        symbol="NEW",
        row_count=100,
        trading_day_count=100,
        earliest_date=date(2025, 10, 1),
        latest_date=date(2026, 3, 15),
    )
    missing = policy.build_symbol_profile(symbol="MISS", row_count=0, trading_day_count=0)

    assert ready.symbol == "AAPL"
    assert ready.status is CoverageStatus.READY
    assert short.status is CoverageStatus.DEGRADED
    assert missing.status is CoverageStatus.FAILED

    profile = UniverseCoverageProfile.from_profiles(
        (ready, short, missing),
        minimum_history_days=252,
        status=CoverageStatus.REVIEW,
    )
    assert profile.canonical_symbol_count == 3
    assert profile.symbols_with_history == 2
    assert profile.symbols_without_history == 1
    assert profile.symbols_meeting_minimum_history == 1
    assert profile.symbols_below_minimum_history == 2
    assert profile.coverage_percentage == 66.6667
    assert profile.minimum_history_percentage == 33.3333
    assert profile.evaluated_symbol_count == 3

    try:
        SymbolCoverageProfile(symbol="", row_count=0)
    except ValueError:
        pass
    else:
        raise AssertionError("blank symbols must be rejected")

    print("Milestone 35 Phase 2 Step 1 coverage contract assertions passed.")


if __name__ == "__main__":
    main()
