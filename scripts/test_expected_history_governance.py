from __future__ import annotations

from datetime import date, datetime, timezone

from trading_ai.trend_intelligence.platform_integration import (
    TrendPlatformIntegrationService,
    TrendPlatformPolicy,
)


def fresh_payload(**values):
    now = datetime.now(timezone.utc)
    return {
        "as_of_date": now.date().isoformat(),
        "snapshot_timestamp": now.isoformat(),
        **values,
    }


def main() -> None:
    service = TrendPlatformIntegrationService(
        session_factory=lambda: None,
        policy=TrendPlatformPolicy(),
    )
    now = datetime.now(timezone.utc)

    expected = service._build_context(
        "FDXF",
        base=fresh_payload(trend_score_adjustment=0.5),
        transition={},
        forecast={},
        institutional={},
        reference_date=date.today(),
        reference_timestamp=now,
        history_rows=44,
    )
    assert expected.status == "READY"
    assert set(expected.expected_warnings) == {
        "MISSING_TRANSITION_TREND_CONTEXT",
        "MISSING_FORECAST_TREND_CONTEXT",
        "MISSING_INSTITUTIONAL_TREND_CONTEXT",
    }
    assert expected.degrading_warnings == ()
    assert expected.history_rows == 44

    unexpected = service._build_context(
        "MATURE",
        base=fresh_payload(trend_score_adjustment=0.5),
        transition={},
        forecast={},
        institutional={},
        reference_date=date.today(),
        reference_timestamp=now,
        history_rows=300,
    )
    assert unexpected.status == "DEGRADED"
    assert not unexpected.expected_warnings
    assert set(unexpected.degrading_warnings) == {
        "MISSING_TRANSITION_TREND_CONTEXT",
        "MISSING_FORECAST_TREND_CONTEXT",
        "MISSING_INSTITUTIONAL_TREND_CONTEXT",
    }

    stale_base = fresh_payload(trend_score_adjustment=0.5)
    stale_base["snapshot_timestamp"] = "2020-01-01T00:00:00+00:00"
    stale = service._build_context(
        "STALE",
        base=stale_base,
        transition={},
        forecast={},
        institutional={},
        reference_date=date.today(),
        reference_timestamp=now,
        history_rows=44,
    )
    assert stale.status == "DEGRADED"
    assert "STALE_BASE_TREND_CONTEXT" in stale.degrading_warnings

    overview = service.market_overview(
        ("FDXF",),
        contexts=[expected],
    )
    assert overview["status"] == "READY"
    assert overview["ready_symbol_count"] == 1
    assert overview["degraded_symbol_count"] == 0
    assert overview["expected_skip_count"] == 3
    assert {item["reason"] for item in overview["expected_skips"]} == {
        "INSUFFICIENT_TRANSITION_HISTORY",
        "INSUFFICIENT_FORECAST_HISTORY",
        "INSUFFICIENT_INSTITUTIONAL_HISTORY",
    }
    assert overview["degrading_warnings"] == []

    print("All expected-history governance assertions passed.")


if __name__ == "__main__":
    main()
