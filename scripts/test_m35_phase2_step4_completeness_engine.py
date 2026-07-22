from datetime import date

from trading_ai.scanner.market_data_quality.completeness import (
    CompletenessStatus,
    MarketDataCompletenessEngine,
    MarketDataCompletenessPolicy,
    WeekdayTradingCalendar,
)


def main() -> None:
    policy = MarketDataCompletenessPolicy(
        lookback_trading_days=5,
        ready_continuity_percentage=100.0,
        degraded_continuity_percentage=80.0,
        review_continuity_percentage=60.0,
    )
    calendar = WeekdayTradingCalendar(holidays=(date(2026, 7, 17),))
    engine = MarketDataCompletenessEngine(policy, calendar)

    # Expected: Jul 13,14,15,16,20 because Jul 17 is configured as a holiday.
    observed = [
        date(2026, 7, 13),
        date(2026, 7, 14),
        date(2026, 7, 15),
        date(2026, 7, 16),
        date(2026, 7, 20),
    ]
    ready = engine.evaluate_symbol("AAPL", observed, as_of_date=date(2026, 7, 20))
    assert ready.status is CompletenessStatus.READY
    assert ready.continuity_percentage == 100.0
    assert not ready.missing_trading_days

    degraded = engine.evaluate_symbol(
        "MSFT", observed[:-1], as_of_date=date(2026, 7, 20)
    )
    assert degraded.status is CompletenessStatus.DEGRADED
    assert degraded.missing_trading_days == (date(2026, 7, 20),)

    duplicate = engine.evaluate_symbol(
        "NVDA", observed + [date(2026, 7, 20)], as_of_date=date(2026, 7, 20)
    )
    assert duplicate.duplicate_row_count == 1
    assert duplicate.status is CompletenessStatus.DEGRADED

    print("Milestone 35 Phase 2 Step 4 completeness engine assertions passed.")


if __name__ == "__main__":
    main()
