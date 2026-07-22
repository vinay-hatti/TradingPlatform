from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any

from .policy import PortfolioAccountPolicy
from .profile import (
    PortfolioAccount,
    PortfolioCashLedgerEntry,
    PortfolioPositionRecord,
    PortfolioRegistrySnapshot,
    utc_now_iso,
)
from .serialization import read_json, write_json_atomic


class PortfolioRegistryService:
    def __init__(
        self,
        registry_file: Path,
        policy: PortfolioAccountPolicy | None = None,
    ) -> None:
        self.registry_file = registry_file
        self.policy = policy or PortfolioAccountPolicy()
        self.policy.validate()

    def initialize(
        self,
        name: str,
        initial_capital: float,
        portfolio_id: str = "PRIMARY",
        metadata: dict[str, Any] | None = None,
    ) -> PortfolioRegistrySnapshot:
        if initial_capital < self.policy.minimum_initial_capital:
            raise ValueError("initial_capital below policy minimum")
        if self.registry_file.exists():
            return self.load_snapshot()

        now = utc_now_iso()
        account = PortfolioAccount(
            portfolio_id=portfolio_id.upper(),
            name=name,
            base_currency=self.policy.base_currency.upper(),
            initial_capital=float(initial_capital),
            created_at=now,
            metadata=dict(metadata or {}),
        )
        ledger = PortfolioCashLedgerEntry(
            entry_id=self._id("CASH", account.portfolio_id, now),
            portfolio_id=account.portfolio_id,
            event_type="INITIAL_CAPITAL",
            amount=float(initial_capital),
            balance_after=float(initial_capital),
            occurred_at=now,
            notes="Portfolio initialized",
        )
        snapshot = PortfolioRegistrySnapshot(
            account=account,
            cash_balance=float(initial_capital),
            net_liquidation_value=float(initial_capital),
            total_capital_committed=0.0,
            total_realized_pnl=0.0,
            total_unrealized_pnl=0.0,
            open_position_count=0,
            closed_position_count=0,
            positions=(),
            cash_ledger=(ledger,),
        )
        self._write(snapshot)
        return snapshot

    def register_position(
        self,
        *,
        symbol: str,
        strategy_id: str,
        strategy_type: str,
        direction: str,
        quantity: int,
        entry_price: float,
        capital_committed: float,
        maximum_loss: float | None = None,
        maximum_profit: float | None = None,
        position_id: str | None = None,
        sector: str = "UNKNOWN",
        industry: str = "UNKNOWN",
        correlation_group: str = "",
        source_artifact: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PortfolioRegistrySnapshot:
        snapshot = self.load_snapshot()
        open_positions = [p for p in snapshot.positions if p.status == "OPEN"]
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if capital_committed <= 0:
            raise ValueError("capital_committed must be positive")
        if len(open_positions) >= self.policy.maximum_open_positions:
            raise ValueError("maximum open positions reached")
        if capital_committed > snapshot.cash_balance and not self.policy.allow_negative_cash:
            raise ValueError("insufficient portfolio cash")

        symbol = symbol.upper()
        strategy_id = strategy_id.upper()
        if not self.policy.allow_duplicate_open_strategy:
            duplicate = any(
                p.symbol == symbol and p.strategy_id == strategy_id
                for p in open_positions
            )
            if duplicate:
                raise ValueError("duplicate open strategy position")

        now = utc_now_iso()
        resolved_id = position_id or self._id(
            "POSITION", snapshot.account.portfolio_id, symbol, strategy_id, now
        )
        position = PortfolioPositionRecord(
            position_id=resolved_id,
            portfolio_id=snapshot.account.portfolio_id,
            symbol=symbol,
            strategy_id=strategy_id,
            strategy_type=strategy_type.upper(),
            direction=direction.upper(),
            status="OPEN",
            quantity=int(quantity),
            entry_price=float(entry_price),
            current_price=float(entry_price),
            capital_committed=float(capital_committed),
            maximum_loss=None if maximum_loss is None else float(maximum_loss),
            maximum_profit=None if maximum_profit is None else float(maximum_profit),
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            opened_at=now,
            updated_at=now,
            sector=sector.upper(),
            industry=industry.upper(),
            correlation_group=correlation_group.upper(),
            source_artifact=source_artifact,
            metadata=dict(metadata or {}),
        )
        new_cash = snapshot.cash_balance - capital_committed
        ledger = PortfolioCashLedgerEntry(
            entry_id=self._id("CASH", resolved_id, now),
            portfolio_id=snapshot.account.portfolio_id,
            event_type="POSITION_OPENED",
            amount=-float(capital_committed),
            balance_after=new_cash,
            occurred_at=now,
            reference_id=resolved_id,
        )
        updated = self._rebuild(
            snapshot,
            positions=tuple(snapshot.positions) + (position,),
            cash_balance=new_cash,
            ledger=tuple(snapshot.cash_ledger) + (ledger,),
        )
        self._write(updated)
        return updated

    def mark_position(self, position_id: str, current_price: float) -> PortfolioRegistrySnapshot:
        snapshot = self.load_snapshot()
        now = utc_now_iso()
        found = False
        updated_positions = []
        for position in snapshot.positions:
            if position.position_id != position_id:
                updated_positions.append(position)
                continue
            if position.status != "OPEN":
                raise ValueError("only open positions can be marked")
            pnl = (float(current_price) - position.entry_price) * position.quantity * self.policy.contract_multiplier
            updated_positions.append(replace(
                position,
                current_price=float(current_price),
                unrealized_pnl=round(pnl, 2),
                updated_at=now,
            ))
            found = True
        if not found:
            raise KeyError(position_id)
        updated = self._rebuild(snapshot, positions=tuple(updated_positions))
        self._write(updated)
        return updated

    def close_position(self, position_id: str, exit_price: float) -> PortfolioRegistrySnapshot:
        snapshot = self.load_snapshot()
        now = utc_now_iso()
        found = None
        updated_positions = []
        for position in snapshot.positions:
            if position.position_id != position_id:
                updated_positions.append(position)
                continue
            if position.status != "OPEN":
                raise ValueError("position is not open")
            realized = (float(exit_price) - position.entry_price) * position.quantity * self.policy.contract_multiplier
            found = replace(
                position,
                status="CLOSED",
                current_price=float(exit_price),
                realized_pnl=round(realized, 2),
                unrealized_pnl=0.0,
                updated_at=now,
                closed_at=now,
            )
            updated_positions.append(found)
        if found is None:
            raise KeyError(position_id)
        cash_credit = found.capital_committed + found.realized_pnl
        new_cash = snapshot.cash_balance + cash_credit
        ledger = PortfolioCashLedgerEntry(
            entry_id=self._id("CASH", position_id, now),
            portfolio_id=snapshot.account.portfolio_id,
            event_type="POSITION_CLOSED",
            amount=round(cash_credit, 2),
            balance_after=round(new_cash, 2),
            occurred_at=now,
            reference_id=position_id,
        )
        updated = self._rebuild(
            snapshot,
            positions=tuple(updated_positions),
            cash_balance=new_cash,
            ledger=tuple(snapshot.cash_ledger) + (ledger,),
        )
        self._write(updated)
        return updated

    def load_snapshot(self) -> PortfolioRegistrySnapshot:
        payload = read_json(self.registry_file)
        if not payload:
            raise FileNotFoundError(self.registry_file)
        account = PortfolioAccount(**payload["account"])
        positions = tuple(PortfolioPositionRecord(**item) for item in payload.get("positions", []))
        ledger = tuple(PortfolioCashLedgerEntry(**item) for item in payload.get("cash_ledger", []))
        return PortfolioRegistrySnapshot(
            account=account,
            cash_balance=float(payload["cash_balance"]),
            net_liquidation_value=float(payload["net_liquidation_value"]),
            total_capital_committed=float(payload["total_capital_committed"]),
            total_realized_pnl=float(payload["total_realized_pnl"]),
            total_unrealized_pnl=float(payload["total_unrealized_pnl"]),
            open_position_count=int(payload["open_position_count"]),
            closed_position_count=int(payload["closed_position_count"]),
            positions=positions,
            cash_ledger=ledger,
            generated_at=str(payload.get("generated_at", utc_now_iso())),
            warnings=tuple(payload.get("warnings", [])),
        )

    def _rebuild(
        self,
        snapshot: PortfolioRegistrySnapshot,
        *,
        positions: tuple[PortfolioPositionRecord, ...] | None = None,
        cash_balance: float | None = None,
        ledger: tuple[PortfolioCashLedgerEntry, ...] | None = None,
    ) -> PortfolioRegistrySnapshot:
        positions = positions if positions is not None else snapshot.positions
        cash = snapshot.cash_balance if cash_balance is None else float(cash_balance)
        committed = sum(p.capital_committed for p in positions if p.status == "OPEN")
        realized = sum(p.realized_pnl for p in positions)
        unrealized = sum(p.unrealized_pnl for p in positions if p.status == "OPEN")
        return PortfolioRegistrySnapshot(
            account=snapshot.account,
            cash_balance=round(cash, 2),
            net_liquidation_value=round(cash + committed + unrealized, 2),
            total_capital_committed=round(committed, 2),
            total_realized_pnl=round(realized, 2),
            total_unrealized_pnl=round(unrealized, 2),
            open_position_count=sum(p.status == "OPEN" for p in positions),
            closed_position_count=sum(p.status == "CLOSED" for p in positions),
            positions=positions,
            cash_ledger=ledger if ledger is not None else snapshot.cash_ledger,
            warnings=(),
        )

    def _write(self, snapshot: PortfolioRegistrySnapshot) -> None:
        write_json_atomic(self.registry_file, snapshot.to_dict())

    @staticmethod
    def _id(prefix: str, *parts: str) -> str:
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16].upper()
        return f"{prefix}-{digest}"
