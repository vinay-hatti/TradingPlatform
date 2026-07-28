from __future__ import annotations

import sys
import types
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.run_market_ingestion import _publish_fresh_option_lineage


class _SessionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakePublisher:
    calls: list[tuple[str, object]] = []

    def __init__(self, session):
        self.session = session

    def publish_option_snapshot(self, **kwargs):
        self.calls.append(("option", kwargs))
        return {
            "status": "READY",
            "rows_written": 123,
            "snapshot_id": kwargs["snapshot_id"],
            "snapshot_timestamp": kwargs["snapshot_timestamp"].isoformat(),
            "completeness_score": 100.0,
        }

    def build_volatility_snapshots(self, **kwargs):
        self.calls.append(("volatility", kwargs))
        return {"status": "READY", "rows_written": 3}

    def build_liquidity_snapshots(self, **kwargs):
        self.calls.append(("liquidity", kwargs))
        return {"status": "READY", "rows_written": 3}


def main() -> None:
    fake_database = types.ModuleType("trading_ai.database")
    fake_database.SessionLocal = lambda: _SessionContext()
    fake_orchestrator = types.ModuleType("trading_ai.market_intelligence.ingestion_orchestrator")
    fake_orchestrator.PolygonDerivedSnapshotPublisher = _FakePublisher

    saved_database = sys.modules.get("trading_ai.database")
    saved_orchestrator = sys.modules.get("trading_ai.market_intelligence.ingestion_orchestrator")
    sys.modules["trading_ai.database"] = fake_database
    sys.modules["trading_ai.market_intelligence.ingestion_orchestrator"] = fake_orchestrator
    try:
        ts = datetime(2026, 7, 27, 19, 46, 48, tzinfo=timezone.utc)
        result = _publish_fresh_option_lineage(
            symbols=("AAPL", "SPX"),
            capture_date=date(2026, 7, 27),
            snapshot_id="options-20260727T194648Z",
            snapshot_timestamp=ts,
        )
    finally:
        if saved_database is None:
            sys.modules.pop("trading_ai.database", None)
        else:
            sys.modules["trading_ai.database"] = saved_database
        if saved_orchestrator is None:
            sys.modules.pop("trading_ai.market_intelligence.ingestion_orchestrator", None)
        else:
            sys.modules["trading_ai.market_intelligence.ingestion_orchestrator"] = saved_orchestrator

    assert [name for name, _ in _FakePublisher.calls] == ["option", "volatility", "liquidity"]
    option_kwargs = _FakePublisher.calls[0][1]
    assert option_kwargs["snapshot_id"] == "options-20260727T194648Z"
    assert option_kwargs["snapshot_timestamp"] == ts
    assert option_kwargs["symbols"] == ("AAPL", "SPX")
    assert result["option_rows"] == 123
    assert result["volatility_rows"] == 3
    assert result["liquidity_rows"] == 3
    print("Milestone 52 Phase 3.7 option lineage publication assertions passed.")


if __name__ == "__main__":
    main()
