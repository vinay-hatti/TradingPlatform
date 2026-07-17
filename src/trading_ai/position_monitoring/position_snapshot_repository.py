from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .position_monitoring_profile import (
    IntradayRiskState,
    MarkedPositionSnapshot,
)


class JsonPositionSnapshotRepository:
    """Append-safe snapshot persistence keyed by snapshot id."""

    def __init__(
        self,
        path: str | Path = "data/position_monitoring/snapshots.json",
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, IntradayRiskState]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        result: dict[str, IntradayRiskState] = {}
        for snapshot_id, raw in payload.get("snapshots", {}).items():
            item = dict(raw)
            item["marked_positions"] = tuple(
                MarkedPositionSnapshot(**position)
                for position in item.get("marked_positions", ())
            )
            result[snapshot_id] = IntradayRiskState(**item)
        return result

    def _save(self, snapshots: dict[str, IntradayRiskState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "snapshots": {
                        snapshot_id: asdict(snapshot)
                        for snapshot_id, snapshot in snapshots.items()
                    }
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def save(self, snapshot: IntradayRiskState) -> IntradayRiskState:
        snapshots = self._load()
        snapshots[snapshot.snapshot_id] = snapshot
        self._save(snapshots)
        return snapshot

    def get(self, snapshot_id: str) -> IntradayRiskState | None:
        return self._load().get(snapshot_id)

    def latest_for_account(
        self,
        account_id: str,
    ) -> IntradayRiskState | None:
        matches = [
            snapshot
            for snapshot in self._load().values()
            if snapshot.account_id == account_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def all_for_account(
        self,
        account_id: str,
    ) -> tuple[IntradayRiskState, ...]:
        return tuple(
            sorted(
                (
                    snapshot
                    for snapshot in self._load().values()
                    if snapshot.account_id == account_id
                ),
                key=lambda item: item.created_at,
            )
        )
