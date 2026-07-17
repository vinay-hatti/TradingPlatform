from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import uuid

from .trading_control_profile import (
    KillSwitchProfile,
    TradingControlState,
    TradingHaltProfile,
)
from .trading_control_repository import JsonTradingControlRepository


class TradingControlService:
    def __init__(
        self,
        repository: JsonTradingControlRepository | None = None,
    ) -> None:
        self.repository = repository or JsonTradingControlRepository()

    def state(self, account_id: str) -> TradingControlState:
        return self.repository.require(account_id)

    def set_manual_kill_switch(
        self,
        *,
        account_id: str,
        active: bool,
        reason: str,
        actor: str,
    ) -> TradingControlState:
        state = self.repository.require(account_id)
        now = datetime.now(timezone.utc).isoformat()
        kill_switch = replace(
            state.kill_switch,
            manual_active=active,
            reason=reason,
            activated_by=actor,
            activated_at=now if active else state.kill_switch.activated_at,
            updated_at=now,
        )
        updated = replace(
            state,
            kill_switch=kill_switch,
            version=state.version + 1,
            updated_at=now,
        )
        return self.repository.save(updated)

    def set_automatic_kill_switch(
        self,
        *,
        account_id: str,
        active: bool,
        reason: str,
    ) -> TradingControlState:
        state = self.repository.require(account_id)
        now = datetime.now(timezone.utc).isoformat()
        kill_switch = replace(
            state.kill_switch,
            automatic_active=active,
            reason=reason,
            activated_by="risk-engine",
            activated_at=now if active else state.kill_switch.activated_at,
            updated_at=now,
        )
        updated = replace(
            state,
            kill_switch=kill_switch,
            version=state.version + 1,
            updated_at=now,
        )
        return self.repository.save(updated)

    def add_halt(
        self,
        *,
        account_id: str,
        scope_type: str,
        scope_value: str,
        reason: str,
        source: str,
        reduce_only: bool = False,
        expires_at: str | None = None,
    ) -> TradingControlState:
        state = self.repository.require(account_id)
        now = datetime.now(timezone.utc).isoformat()
        halt = TradingHaltProfile(
            halt_id=f"halt-{uuid.uuid4().hex}",
            scope_type=scope_type.upper(),
            scope_value=scope_value.upper(),
            active=True,
            reason=reason,
            source=source,
            reduce_only=reduce_only,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        updated = replace(
            state,
            halts=(*state.halts, halt),
            version=state.version + 1,
            updated_at=now,
        )
        return self.repository.save(updated)

    def clear_halt(
        self,
        *,
        account_id: str,
        halt_id: str,
    ) -> TradingControlState:
        state = self.repository.require(account_id)
        now = datetime.now(timezone.utc).isoformat()
        halts = tuple(
            replace(halt, active=False, updated_at=now)
            if halt.halt_id == halt_id
            else halt
            for halt in state.halts
        )
        updated = replace(
            state,
            halts=halts,
            version=state.version + 1,
            updated_at=now,
        )
        return self.repository.save(updated)
