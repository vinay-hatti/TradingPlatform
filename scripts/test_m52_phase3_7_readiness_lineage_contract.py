from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from trading_ai.market_intelligence.publication import ScannerReadinessService


class _Result:
    def __init__(self, *, mapping=None, scalar=None):
        self._mapping = mapping
        self._scalar = scalar

    def mappings(self):
        return self

    def one_or_none(self):
        return self._mapping

    def scalar_one_or_none(self):
        return self._scalar


class _Session:
    def __init__(self, *, coherent: bool):
        self.coherent = coherent
        self.now = datetime(2026, 7, 27, 19, 46, 48, tzinfo=timezone.utc)

    def execute(self, statement, params=None):
        sql = str(statement)
        if "SELECT snapshot_timestamp, as_of_date" in sql and "FROM market_intelligence_snapshot" in sql:
            return _Result(mapping={"snapshot_timestamp": self.now, "as_of_date": date(2026, 7, 27)})
        if "FROM option_snapshot_run run" in sql:
            mapping = None
            if self.coherent:
                mapping = {
                    "id": 2,
                    "snapshot_id": "options-fresh",
                    "snapshot_timestamp": self.now,
                    "as_of_date": date(2026, 7, 27),
                    "capture_status": "READY",
                    "contracts_persisted": 100,
                    "completeness_score": 100.0,
                }
            return _Result(mapping=mapping)
        if "FROM option_snapshot_run" in sql:
            return _Result(mapping={
                "id": 2,
                "snapshot_id": "options-fresh",
                "snapshot_timestamp": self.now,
                "as_of_date": date(2026, 7, 27),
                "capture_status": "READY",
                "contracts_persisted": 100,
                "completeness_score": 100.0,
            })
        if "COUNT(*)" in sql:
            return _Result(scalar=100)
        if "MAX(" in sql:
            return _Result(scalar=str(self.now))
        raise AssertionError(f"Unexpected SQL: {sql}")


def main() -> None:
    healthy = ScannerReadinessService(_Session(coherent=True)).evaluate()
    lineage = next(check for check in healthy.checks if check.name == "option_snapshot_lineage")
    assert lineage.status == "READY"
    assert healthy.status == "READY"
    assert healthy.option_snapshot_id == "options-fresh"

    broken = ScannerReadinessService(_Session(coherent=False)).evaluate()
    lineage = next(check for check in broken.checks if check.name == "option_snapshot_lineage")
    assert lineage.status == "FAILED"
    assert not broken.scanner_ready
    assert broken.status == "FAILED"
    print("Milestone 52 Phase 3.7 readiness lineage contract assertions passed.")


if __name__ == "__main__":
    main()
