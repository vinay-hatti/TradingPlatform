from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .paper_trading_profile import (
    PaperTradingCycleProfile,
    PaperTradingRuntimeState,
    PaperTradingSessionProfile,
)


class JsonPaperTradingRuntimeRepository:
    """Atomic JSON persistence for paper-trading runtime state."""

    def __init__(
        self,
        path: str | Path = "data/paper_trading/runtime_states.json",
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, PaperTradingRuntimeState]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        result: dict[str, PaperTradingRuntimeState] = {}
        for session_id, raw in payload.get("sessions", {}).items():
            item = dict(raw)
            item["session"] = PaperTradingSessionProfile(**item["session"])
            if item.get("last_cycle") is not None:
                item["last_cycle"] = PaperTradingCycleProfile(
                    **item["last_cycle"]
                )
            result[session_id] = PaperTradingRuntimeState(**item)
        return result

    def _save(
        self,
        states: dict[str, PaperTradingRuntimeState],
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sessions": {
                session_id: asdict(state)
                for session_id, state in states.items()
            }
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def get(self, session_id: str) -> PaperTradingRuntimeState | None:
        return self._load().get(session_id)

    def require(self, session_id: str) -> PaperTradingRuntimeState:
        state = self.get(session_id)
        if state is None:
            raise KeyError(f"Paper-trading session not found: {session_id}")
        return state

    def save(
        self,
        state: PaperTradingRuntimeState,
    ) -> PaperTradingRuntimeState:
        states = self._load()
        states[state.session.session_id] = state
        self._save(states)
        return state

    def all(self) -> tuple[PaperTradingRuntimeState, ...]:
        return tuple(self._load().values())
