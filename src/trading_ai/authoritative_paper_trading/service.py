from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trading_ai.paper_trading.paper_execution_profile import PaperExecutionRecord
from trading_ai.paper_trading.paper_position_engine import PaperPositionEngine
from trading_ai.portfolio_management.database_models import (
    PortfolioAccountModel,
    PortfolioCashLedgerModel,
    PortfolioPositionModel,
)

from .database_models import (
    PaperExecutionModel,
    PaperPositionLifecycleEventModel,
    PortfolioCashReservationModel,
)
from .repositories import DatabasePaperExecutionRepository, DatabasePaperPositionRepository


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()[:24]
    return f"{prefix}-{digest.upper()}"


class AuthoritativePaperAccountService:
    """Transactional paper-account accounting over existing portfolio tables.

    The service deliberately owns the commit boundary. A paper fill, its cash
    movement, reservation release, position update and lifecycle event either
    all persist or all roll back.
    """

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        if session_factory is None:
            from trading_ai.database.session import create_session
            session_factory = create_session
        self.session_factory = session_factory
        self.position_engine = PaperPositionEngine()

    def create_account(
        self,
        *,
        account_id: str,
        name: str,
        initial_capital: float,
        base_currency: str = "USD",
        metadata: dict | None = None,
    ) -> dict:
        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        session = self.session_factory()
        try:
            with session.begin():
                existing = session.get(PortfolioAccountModel, account_id)
                if existing is None:
                    now = utc_now_iso()
                    session.add(PortfolioAccountModel(
                        portfolio_id=account_id,
                        name=name,
                        base_currency=base_currency,
                        initial_capital=initial_capital,
                        status="ACTIVE",
                        created_at=now,
                        metadata_json={**(metadata or {}), "account_type": "PAPER"},
                    ))
                    session.add(PortfolioCashLedgerModel(
                        entry_id=stable_id("LEDGER", account_id, "INITIAL_CAPITAL"),
                        portfolio_id=account_id,
                        event_type="INITIAL_CAPITAL",
                        amount=initial_capital,
                        balance_after=initial_capital,
                        occurred_at=now,
                        reference_id=account_id,
                        notes="Authoritative paper-account initialization",
                    ))
            return self.account_summary(account_id)
        finally:
            session.close()

    def reserve_buying_power(
        self,
        *,
        account_id: str,
        aggregate_id: str,
        amount: float,
        metadata: dict | None = None,
    ) -> dict:
        if amount <= 0:
            raise ValueError("reservation amount must be positive")
        session = self.session_factory()
        try:
            with session.begin():
                self._require_account(session, account_id)
                existing = session.scalar(select(PortfolioCashReservationModel).where(
                    PortfolioCashReservationModel.aggregate_id == aggregate_id
                ))
                if existing is not None:
                    if existing.portfolio_id != account_id or abs(existing.amount - amount) > 1e-8:
                        raise ValueError("aggregate already has a different reservation")
                    return self._reservation_dict(existing)
                available = self._available_cash(session, account_id)
                if amount > available + 1e-8:
                    raise ValueError(f"insufficient available cash: requested={amount:.2f}, available={available:.2f}")
                reservation = PortfolioCashReservationModel(
                    reservation_id=stable_id("RESV", account_id, aggregate_id),
                    portfolio_id=account_id,
                    aggregate_id=aggregate_id,
                    amount=amount,
                    status="ACTIVE",
                    reserved_at=utc_now_iso(),
                    released_at=None,
                    release_reason=None,
                    metadata_json=metadata or {},
                )
                session.add(reservation)
                session.flush()
                return self._reservation_dict(reservation)
        finally:
            session.close()

    def release_reservation(self, *, aggregate_id: str, reason: str) -> dict | None:
        session = self.session_factory()
        try:
            with session.begin():
                reservation = session.scalar(select(PortfolioCashReservationModel).where(
                    PortfolioCashReservationModel.aggregate_id == aggregate_id
                ))
                if reservation is None:
                    return None
                if reservation.status == "ACTIVE":
                    reservation.status = "RELEASED"
                    reservation.released_at = utc_now_iso()
                    reservation.release_reason = reason
                return self._reservation_dict(reservation)
        finally:
            session.close()

    def settle_execution(
        self,
        record: PaperExecutionRecord,
        *,
        asset_class: str,
        multiplier: int,
    ) -> dict:
        """Persist execution and atomically account for its fills.

        Replaying the same execution_key is idempotent and returns the existing
        account state without posting duplicate ledger or position events.
        """
        session = self.session_factory()
        try:
            with session.begin():
                self._require_account(session, record.account_id)
                existing = session.get(PaperExecutionModel, record.execution_key)
                if existing is not None:
                    return self._settlement_result(session, record.account_id, record.execution_key, replayed=True)

                DatabasePaperExecutionRepository(session).save(record)
                cash_delta = self._cash_delta(record, multiplier)
                previous_balance = self._cash_balance(session, record.account_id)
                new_balance = previous_balance + cash_delta
                if new_balance < -1e-8:
                    raise ValueError(f"execution would overdraw paper account by ${abs(new_balance):.2f}")

                session.add(PortfolioCashLedgerModel(
                    entry_id=stable_id("LEDGER", record.account_id, record.execution_key),
                    portfolio_id=record.account_id,
                    event_type="PAPER_EXECUTION_SETTLEMENT",
                    amount=cash_delta,
                    balance_after=new_balance,
                    occurred_at=record.updated_at,
                    reference_id=record.execution_key,
                    notes=f"Paper execution settlement for {record.aggregate_id}",
                ))

                reservation = session.scalar(select(PortfolioCashReservationModel).where(
                    PortfolioCashReservationModel.aggregate_id == record.aggregate_id
                ))
                if reservation is not None and reservation.status == "ACTIVE":
                    reservation.status = "CONSUMED"
                    reservation.released_at = record.updated_at
                    reservation.release_reason = "EXECUTION_SETTLED"

                decision = self.position_engine.open_from_execution(
                    record,
                    asset_class=asset_class,
                    multiplier=multiplier,
                )
                if decision.allowed and decision.position is not None:
                    position_repo = DatabasePaperPositionRepository(session)
                    current = position_repo.get(decision.position.position_id)
                    if current is None:
                        position_repo.save(decision.position)
                        session.add(PaperPositionLifecycleEventModel(
                            event_id=stable_id("POSEVT", decision.position.position_id, record.execution_key, "OPEN"),
                            position_id=decision.position.position_id,
                            portfolio_id=record.account_id,
                            event_type="POSITION_OPENED",
                            quantity=decision.position.quantity,
                            price=decision.position.average_cost,
                            realized_pnl=0.0,
                            occurred_at=record.updated_at,
                            reference_id=record.execution_key,
                            metadata_json={"aggregate_id": record.aggregate_id, "fill_ids": [f.fill_id for f in record.fills]},
                        ))
                session.flush()
                return self._settlement_result(session, record.account_id, record.execution_key, replayed=False)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def account_summary(self, account_id: str) -> dict:
        session = self.session_factory()
        try:
            self._require_account(session, account_id)
            return self._summary(session, account_id)
        finally:
            session.close()

    def reconcile(self, account_id: str) -> dict:
        session = self.session_factory()
        try:
            account = self._require_account(session, account_id)
            ledger_rows = session.scalars(select(PortfolioCashLedgerModel).where(
                PortfolioCashLedgerModel.portfolio_id == account_id
            ).order_by(PortfolioCashLedgerModel.occurred_at, PortfolioCashLedgerModel.entry_id)).all()
            running = sum(float(row.amount) for row in ledger_rows)
            errors: list[str] = []
            if ledger_rows and abs(running - self._cash_balance(session, account_id)) > 1e-6:
                errors.append("FINAL_LEDGER_BALANCE_MISMATCH")
            if len({row.entry_id for row in ledger_rows}) != len(ledger_rows):
                errors.append("DUPLICATE_LEDGER_ENTRY_ID")
            active_reserved = self._reserved_cash(session, account_id)
            if active_reserved < -1e-8:
                errors.append("NEGATIVE_RESERVED_CASH")
            orphan_positions = session.scalar(select(func.count()).select_from(PortfolioPositionModel).where(
                PortfolioPositionModel.portfolio_id == account_id,
                PortfolioPositionModel.metadata_json["aggregate_id"].as_string().isnot(None),
            )) or 0
            return {
                "account_id": account_id,
                "status": "READY" if not errors else "FAILED",
                "ledger_entries": len(ledger_rows),
                "cash_balance": round(running if ledger_rows else account.initial_capital, 6),
                "reserved_cash": round(active_reserved, 6),
                "paper_positions": int(orphan_positions),
                "errors": errors,
            }
        finally:
            session.close()

    @staticmethod
    def _cash_delta(record: PaperExecutionRecord, multiplier: int) -> float:
        delta = 0.0
        for fill in record.fills:
            gross = abs(fill.quantity) * fill.fill_price * multiplier
            if fill.side.upper().startswith("BUY"):
                delta -= gross + fill.commission
            else:
                delta += gross - fill.commission
        return round(delta, 8)

    def _settlement_result(self, session: Session, account_id: str, execution_key: str, *, replayed: bool) -> dict:
        result = self._summary(session, account_id)
        result.update({"execution_key": execution_key, "replayed": replayed, "status": "SETTLED"})
        return result

    def _summary(self, session: Session, account_id: str) -> dict:
        cash = self._cash_balance(session, account_id)
        reserved = self._reserved_cash(session, account_id)
        positions = session.scalars(select(PortfolioPositionModel).where(
            PortfolioPositionModel.portfolio_id == account_id
        )).all()
        market_value = sum(float(p.metadata_json.get("market_value", p.current_price * p.quantity)) for p in positions)
        realized = sum(p.realized_pnl for p in positions)
        unrealized = sum(p.unrealized_pnl for p in positions)
        return {
            "account_id": account_id,
            "cash_balance": round(cash, 6),
            "reserved_cash": round(reserved, 6),
            "available_cash": round(cash - reserved, 6),
            "position_market_value": round(market_value, 6),
            "net_liquidation_value": round(cash + market_value, 6),
            "realized_pnl": round(realized, 6),
            "unrealized_pnl": round(unrealized, 6),
            "position_count": len(positions),
        }

    @staticmethod
    def _require_account(session: Session, account_id: str) -> PortfolioAccountModel:
        account = session.get(PortfolioAccountModel, account_id)
        if account is None:
            raise KeyError(f"paper account not found: {account_id}")
        return account

    @staticmethod
    def _cash_balance(session: Session, account_id: str) -> float:
        # The ledger is additive and idempotent by entry_id. Summing amounts is
        # authoritative even when an imported execution carries an older event
        # timestamp than account initialization or another persisted event.
        total = session.scalar(select(func.coalesce(func.sum(PortfolioCashLedgerModel.amount), 0.0)).where(
            PortfolioCashLedgerModel.portfolio_id == account_id
        ))
        if total is not None and abs(float(total)) > 1e-12:
            return float(total)
        account = session.get(PortfolioAccountModel, account_id)
        return float(account.initial_capital if account is not None else 0.0)

    @staticmethod
    def _reserved_cash(session: Session, account_id: str) -> float:
        value = session.scalar(select(func.coalesce(func.sum(PortfolioCashReservationModel.amount), 0.0)).where(
            PortfolioCashReservationModel.portfolio_id == account_id,
            PortfolioCashReservationModel.status == "ACTIVE",
        ))
        return float(value or 0.0)

    def _available_cash(self, session: Session, account_id: str) -> float:
        return self._cash_balance(session, account_id) - self._reserved_cash(session, account_id)

    @staticmethod
    def _reservation_dict(model: PortfolioCashReservationModel) -> dict:
        return {
            "reservation_id": model.reservation_id,
            "portfolio_id": model.portfolio_id,
            "aggregate_id": model.aggregate_id,
            "amount": model.amount,
            "status": model.status,
            "reserved_at": model.reserved_at,
            "released_at": model.released_at,
            "release_reason": model.release_reason,
            "metadata": model.metadata_json or {},
        }
