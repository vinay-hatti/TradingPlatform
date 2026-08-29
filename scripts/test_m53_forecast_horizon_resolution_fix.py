from __future__ import annotations

from datetime import date

from trading_ai.trend_intelligence.forecast_repository import (
    TrendForecastRepository,
    _business_day_age,
)


def main() -> None:
    assert _business_day_age(date(2026, 7, 24), date(2026, 7, 28)) == 2

    repo = TrendForecastRepository()
    cases = (("NDX", 2, 5), ("SPX", 63, 20), ("RUT", 10, 10))
    for symbol, requested, expected in cases:
        payload = repo.latest(
            symbol,
            horizon_days=requested,
            reference_date=date(2026, 7, 28),
        )
        assert payload is not None, (symbol, requested)
        assert payload["forecast_resolved_horizon_days"] == expected, payload
        expected_mode = "EXACT" if requested == expected else "NEAREST_AVAILABLE"
        assert payload["forecast_horizon_resolution"] == expected_mode, payload

        context = repo.scanner_context(
            symbol=symbol,
            signal="CALL",
            horizon_days=requested,
            maximum_age_days=3,
            reference_date=date(2026, 7, 28),
        )
        assert context["forecast_context_status"] in {
            "FRESH",
            "FRESH_APPROXIMATE_HORIZON",
        }, context
        assert context["forecast_direction"] != "UNAVAILABLE", context
        assert context["forecast_resolved_horizon_days"] == expected, context

    print("Milestone 53 forecast horizon resolution assertions passed.")


if __name__ == "__main__":
    main()
