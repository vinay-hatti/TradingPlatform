from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from trading_ai.published_state import (
    PublishedMarketStateResolver,
    PublishedStateFailureCode,
    PublishedStateNotReadyError,
    PublishedStatePolicy,
    PublishedStateStaleError,
)


class Result:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def one_or_none(self):
        return self.row


class Session:
    def __init__(self, row):
        self.row = row

    def execute(self, *_args, **_kwargs):
        return Result(self.row)


def row(**overrides):
    now = datetime(2026, 7, 25, 20, 0, tzinfo=timezone.utc)
    values = {
        "publication_name": "current_market_state",
        "run_id": "run-1",
        "published_at": now - timedelta(hours=2),
        "as_of_date": date(2026, 7, 23),
        "market_intelligence_timestamp": now - timedelta(hours=2),
        "option_snapshot_timestamp": now - timedelta(hours=8),
        "option_snapshot_id": "polygon-snapshot-1",
        "readiness_status": "DEGRADED",
        "scanner_ready": True,
        "decision_context_ready": True,
        "details_json": {"option_snapshot_completeness_pct": 99.5},
    }
    values.update(overrides)
    return values


def main():
    now = datetime(2026, 7, 25, 20, 0, tzinfo=timezone.utc)

    scanner = PublishedStatePolicy.for_consumer("scanner")
    decision = PublishedStatePolicy.for_consumer("decision")
    assert scanner.require_scanner_ready and not scanner.require_decision_context_ready
    assert decision.require_decision_context_ready and not decision.require_scanner_ready

    usable = PublishedMarketStateResolver(Session(row()), scanner).resolve(now=now)
    assert usable.usable
    assert PublishedStateFailureCode.STATUS_NOT_READY.value in usable.warning_codes
    assert not usable.failure_codes

    warning_policy = PublishedStatePolicy.for_consumer(
        "scanner", maximum_age_seconds=10 * 3600, warning_age_seconds=4 * 3600
    )
    warning = PublishedMarketStateResolver(
        Session(row(published_at=now - timedelta(hours=5))), warning_policy
    ).resolve(now=now)
    assert warning.usable
    assert PublishedStateFailureCode.PUBLICATION_STALE.value in warning.warning_codes

    stale = PublishedMarketStateResolver(
        Session(row(published_at=now - timedelta(hours=40))), scanner
    ).resolve(now=now)
    assert not stale.usable
    assert PublishedStateFailureCode.PUBLICATION_STALE.value in stale.failure_codes
    try:
        PublishedMarketStateResolver(
            Session(row(published_at=now - timedelta(hours=40))), scanner
        ).require(now=now)
    except PublishedStateStaleError as exc:
        assert PublishedStateFailureCode.PUBLICATION_STALE.value in exc.codes
    else:
        raise AssertionError("Expected PublishedStateStaleError")

    unready = PublishedMarketStateResolver(
        Session(row(scanner_ready=False)), scanner
    ).resolve(now=now)
    assert PublishedStateFailureCode.SCANNER_NOT_READY.value in unready.failure_codes

    decision_unready = PublishedMarketStateResolver(
        Session(row(decision_context_ready=False)), decision
    ).resolve(now=now)
    assert PublishedStateFailureCode.DECISION_CONTEXT_NOT_READY.value in decision_unready.failure_codes

    missing_lineage = PublishedMarketStateResolver(
        Session(row(option_snapshot_id=None)), scanner
    ).resolve(now=now)
    assert PublishedStateFailureCode.OPTION_SNAPSHOT_MISSING.value in missing_lineage.failure_codes

    strict = PublishedStatePolicy.for_consumer("scanner", allow_degraded=False)
    rejected = PublishedMarketStateResolver(Session(row()), strict).resolve(now=now)
    assert PublishedStateFailureCode.DEGRADED_NOT_ALLOWED.value in rejected.failure_codes
    try:
        PublishedMarketStateResolver(Session(row()), strict).require(now=now)
    except PublishedStateNotReadyError as exc:
        assert PublishedStateFailureCode.DEGRADED_NOT_ALLOWED.value in exc.codes
    else:
        raise AssertionError("Expected PublishedStateNotReadyError")

    print("Milestone 47 Phase 4 staleness and failure governance assertions passed.")


if __name__ == "__main__":
    main()
