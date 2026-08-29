from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from trading_ai.published_state import PublishedStatePolicy
from trading_ai.published_state.service import PublishedMarketStateResolver


class Result:
    def __init__(self, row): self.row = row
    def mappings(self): return self
    def one_or_none(self): return self.row


class Session:
    def __init__(self, row): self.row = row
    def execute(self, *_args, **_kwargs): return Result(self.row)


now = datetime(2026, 7, 25, 22, 0, tzinfo=timezone.utc)
base = {
    "publication_name": "current_market_state",
    "run_id": "run-47",
    "published_at": now - timedelta(hours=1),
    "as_of_date": date(2026, 7, 23),
    "market_intelligence_timestamp": now - timedelta(hours=2),
    "option_snapshot_timestamp": now - timedelta(hours=8),
    "option_snapshot_id": "polygon-snapshot",
    "readiness_status": "DEGRADED",
    "scanner_ready": True,
    "decision_context_ready": True,
    "details_json": '{"coverage":99.5}',
}
policy = PublishedStatePolicy(require_scanner_ready=True, maximum_age_seconds=7200)
result = PublishedMarketStateResolver(Session(base), policy).resolve(now=now)
assert result.usable
assert result.status == "DEGRADED"
assert result.state and result.state.option_snapshot_id == "polygon-snapshot"
assert result.warnings

stale = dict(base, published_at=now - timedelta(hours=3))
result = PublishedMarketStateResolver(Session(stale), policy).resolve(now=now)
assert not result.usable
assert any("stale" in value.lower() for value in result.errors)

not_ready = dict(base, scanner_ready=False)
result = PublishedMarketStateResolver(Session(not_ready), policy).resolve(now=now)
assert not result.usable

missing = PublishedMarketStateResolver(Session(None), policy).resolve(now=now)
assert missing.status == "UNAVAILABLE"
assert not missing.usable

source = Path("src/trading_ai/published_state/service.py").read_text()
assert "independently selected latest rows" in source
print("Milestone 47 Phase 1 published-state resolver assertions passed.")
