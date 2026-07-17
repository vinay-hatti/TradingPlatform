from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .portfolio_greeks_profile import (
    GreeksExposureSurfacePoint,
    PortfolioGreeksRiskState,
    UnderlyingGreeksExposure,
)


class JsonPortfolioGreeksRepository:
    def __init__(
        self,
        path: str | Path = "data/position_monitoring/portfolio_greeks.json",
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, PortfolioGreeksRiskState]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        result = {}
        for snapshot_id, raw in payload.get("snapshots", {}).items():
            item = dict(raw)
            item["surface_points"] = tuple(
                GreeksExposureSurfacePoint(**point)
                for point in item.get("surface_points", ())
            )
            underlyings = []
            for exposure in item.get("by_underlying", ()):
                exposure = dict(exposure)
                exposure["surface_points"] = tuple(
                    GreeksExposureSurfacePoint(**point)
                    for point in exposure.get("surface_points", ())
                )
                underlyings.append(UnderlyingGreeksExposure(**exposure))
            item["by_underlying"] = tuple(underlyings)
            result[snapshot_id] = PortfolioGreeksRiskState(**item)
        return result

    def _save(self, states: dict[str, PortfolioGreeksRiskState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(
                {
                    "snapshots": {
                        key: asdict(value) for key, value in states.items()
                    }
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)

    def save(self, state: PortfolioGreeksRiskState) -> PortfolioGreeksRiskState:
        states = self._load()
        states[state.snapshot_id] = state
        self._save(states)
        return state

    def get(self, snapshot_id: str) -> PortfolioGreeksRiskState | None:
        return self._load().get(snapshot_id)

    def latest_for_account(
        self,
        account_id: str,
    ) -> PortfolioGreeksRiskState | None:
        matches = [
            state for state in self._load().values()
            if state.account_id == account_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda state: state.created_at)
