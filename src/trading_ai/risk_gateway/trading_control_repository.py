from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .trading_control_profile import (
    KillSwitchProfile,
    TradingControlState,
    TradingHaltProfile,
)


class JsonTradingControlRepository:
    """Persist kill-switch and halt state with versioned atomic writes."""

    def __init__(
        self,
        path: str | Path = "data/risk_gateway/trading_controls.json",
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, TradingControlState]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        result: dict[str, TradingControlState] = {}
        for account_id, raw in payload.get("accounts", {}).items():
            item = dict(raw)
            item["kill_switch"] = KillSwitchProfile(**item["kill_switch"])
            item["halts"] = tuple(
                TradingHaltProfile(**halt)
                for halt in item.get("halts", ())
            )
            result[account_id] = TradingControlState(**item)
        return result

    def _save(self, states: dict[str, TradingControlState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "accounts": {
                account_id: asdict(state)
                for account_id, state in states.items()
            }
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def get(self, account_id: str) -> TradingControlState | None:
        return self._load().get(account_id)

    def require(self, account_id: str) -> TradingControlState:
        state = self.get(account_id)
        if state is None:
            state = TradingControlState(
                account_id=account_id,
                kill_switch=KillSwitchProfile(account_id=account_id),
            )
            self.save(state)
        return state

    def save(self, state: TradingControlState) -> TradingControlState:
        states = self._load()
        states[state.account_id] = state
        self._save(states)
        return state
