from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from trading_ai.trend_intelligence.platform_integration import (
    TrendPlatformIntegrationService,
    TrendPlatformPolicy,
)


def main() -> None:
    service = TrendPlatformIntegrationService(
        session_factory=None,
        policy=TrendPlatformPolicy(maximum_age_days=3),
    )
    now = datetime.now(timezone.utc)

    # A current governed row timestamp wins even when as_of_date is historical.
    assert service._is_fresh(
        {
            "as_of_date": "2020-01-01",
            "snapshot_timestamp": (now - timedelta(minutes=5)).isoformat(),
        },
        reference_date=now.date(),
        reference_timestamp=now,
    )

    # An actually stale row timestamp remains stale.
    assert not service._is_fresh(
        {
            "as_of_date": date.today().isoformat(),
            "snapshot_timestamp": (now - timedelta(days=4)).isoformat(),
        },
        reference_date=now.date(),
        reference_timestamp=now,
    )

    # as_of_date is a fallback only when snapshot_timestamp is unavailable.
    assert service._is_fresh(
        {"as_of_date": now.date().isoformat(), "snapshot_timestamp": None},
        reference_date=now.date(),
        reference_timestamp=now,
    )

    print("All Trend Platform freshness authority assertions passed.")


if __name__ == "__main__":
    main()
