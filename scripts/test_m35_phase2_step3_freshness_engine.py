from datetime import date
from trading_ai.scanner.market_data_quality import (
    CoverageStatus, MarketDataCoveragePolicy, MarketDataFreshnessEngine,
    WeekdayTradingCalendar,
)

def main():
    coverage_policy = MarketDataCoveragePolicy(minimum_history_days=1)
    profiles = [
        coverage_policy.build_symbol_profile(symbol="AAPL", row_count=5, trading_day_count=5, earliest_date=date(2026,7,13), latest_date=date(2026,7,17)),
        coverage_policy.build_symbol_profile(symbol="MSFT", row_count=5, trading_day_count=5, earliest_date=date(2026,7,13), latest_date=date(2026,7,16)),
        coverage_policy.build_symbol_profile(symbol="NVDA", row_count=0, trading_day_count=0),
    ]
    coverage = coverage_policy.evaluate(profiles)
    engine = MarketDataFreshnessEngine(calendar=WeekdayTradingCalendar())
    result = engine.evaluate(coverage, as_of_date=date(2026,7,20))
    assert result.expected_latest_trading_date == date(2026,7,20)
    by_symbol = {x.symbol: x for x in result.symbol_profiles}
    assert by_symbol["AAPL"].staleness_days == 1
    assert by_symbol["AAPL"].status is CoverageStatus.DEGRADED
    assert by_symbol["MSFT"].staleness_days == 2
    assert by_symbol["MSFT"].status is CoverageStatus.REVIEW
    assert by_symbol["NVDA"].status is CoverageStatus.FAILED
    print("Milestone 35 Phase 2 Step 3 freshness engine assertions passed.")

if __name__ == "__main__": main()
