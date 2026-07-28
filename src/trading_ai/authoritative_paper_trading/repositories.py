from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from trading_ai.order_management.order_profile import CanonicalOrderAggregate, CanonicalOrderEvent, CanonicalOrderLeg
from trading_ai.order_management.order_repository_exceptions import DuplicateOrderError, OptimisticConcurrencyError, OrderNotFoundError
from trading_ai.order_management.order_repository_profile import OrderPersistenceResult
from trading_ai.paper_trading.paper_execution_profile import PaperExecutionRecord, PaperFillProfile
from trading_ai.paper_trading.paper_position_profile import PaperPositionLot, PaperPositionProfile
from trading_ai.portfolio_management.database_models import PortfolioPositionModel

from .database_models import (
    CanonicalOrderEventModel,
    CanonicalOrderModel,
    PaperAutomationCheckpointModel,
    PaperExecutionModel,
    PaperFillModel,
    PaperPositionLifecycleEventModel,
    PaperPositionMarkModel,
    PaperTradingControlModel,
    PaperTradingSessionModel,
    PortfolioCashReservationModel,
)


class DatabaseOrderRepository:
    """Canonical OMS repository backed by the caller's SQLAlchemy transaction."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _aggregate(model: CanonicalOrderModel) -> CanonicalOrderAggregate:
        return CanonicalOrderAggregate(
            aggregate_id=model.aggregate_id,
            client_order_id=model.client_order_id,
            account_id=model.account_id,
            idempotency_key=model.idempotency_key,
            order_type=model.order_type,
            time_in_force=model.time_in_force,
            legs=tuple(CanonicalOrderLeg(**leg) for leg in model.legs_json),
            state=model.state,
            version=model.version,
            total_quantity=model.total_quantity,
            filled_quantity=model.filled_quantity,
            remaining_quantity=model.remaining_quantity,
            average_fill_price=model.average_fill_price,
            limit_price=model.limit_price,
            stop_price=model.stop_price,
            outside_regular_hours=model.outside_regular_hours,
            strategy_name=model.strategy_name,
            broker_order_id=model.broker_order_id,
            parent_aggregate_id=model.parent_aggregate_id,
            root_aggregate_id=model.root_aggregate_id,
            replace_count=model.replace_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
            terminal_at=model.terminal_at,
            last_event_id=model.last_event_id,
            metadata=model.metadata_json or {},
        )

    @staticmethod
    def _values(aggregate: CanonicalOrderAggregate) -> dict:
        payload = asdict(aggregate)
        payload["legs_json"] = payload.pop("legs")
        payload["metadata_json"] = payload.pop("metadata")
        return payload

    def get(self, aggregate_id: str) -> CanonicalOrderAggregate | None:
        model = self.session.get(CanonicalOrderModel, aggregate_id)
        return None if model is None else self._aggregate(model)

    def require(self, aggregate_id: str) -> CanonicalOrderAggregate:
        aggregate = self.get(aggregate_id)
        if aggregate is None:
            raise OrderNotFoundError(f"Order aggregate not found: {aggregate_id}")
        return aggregate

    def all(self) -> tuple[CanonicalOrderAggregate, ...]:
        rows = self.session.scalars(select(CanonicalOrderModel).order_by(CanonicalOrderModel.created_at)).all()
        return tuple(self._aggregate(row) for row in rows)

    def create(self, aggregate: CanonicalOrderAggregate) -> OrderPersistenceResult:
        if self.session.get(CanonicalOrderModel, aggregate.aggregate_id) is not None:
            raise DuplicateOrderError(f"Order aggregate already exists: {aggregate.aggregate_id}")
        self.session.add(CanonicalOrderModel(**self._values(aggregate)))
        self.session.flush()
        return OrderPersistenceResult(valid=True, allowed=True, action="CREATE", aggregate_id=aggregate.aggregate_id, expected_version=None, actual_version=None, persisted_version=aggregate.version, aggregate=aggregate, recommendation="PERSISTED")

    def save(self, aggregate: CanonicalOrderAggregate, *, expected_version: int) -> OrderPersistenceResult:
        model = self.session.get(CanonicalOrderModel, aggregate.aggregate_id)
        if model is None:
            raise OrderNotFoundError(f"Order aggregate not found: {aggregate.aggregate_id}")
        actual_version = model.version
        if expected_version != actual_version or aggregate.version != actual_version + 1:
            raise OptimisticConcurrencyError(aggregate.aggregate_id, expected_version, actual_version)
        for key, value in self._values(aggregate).items():
            setattr(model, key, value)
        self.session.flush()
        return OrderPersistenceResult(valid=True, allowed=True, action="UPDATE", aggregate_id=aggregate.aggregate_id, expected_version=expected_version, actual_version=actual_version, persisted_version=aggregate.version, aggregate=aggregate, recommendation="PERSISTED")

    def delete(self, aggregate_id: str, *, expected_version: int) -> OrderPersistenceResult:
        model = self.session.get(CanonicalOrderModel, aggregate_id)
        if model is None:
            raise OrderNotFoundError(f"Order aggregate not found: {aggregate_id}")
        aggregate = self._aggregate(model)
        if model.version != expected_version:
            raise OptimisticConcurrencyError(aggregate_id, expected_version, model.version)
        self.session.delete(model)
        self.session.flush()
        return OrderPersistenceResult(valid=True, allowed=True, action="DELETE", aggregate_id=aggregate_id, expected_version=expected_version, actual_version=expected_version, persisted_version=None, aggregate=aggregate, recommendation="DELETED")

    def append_event(self, event: CanonicalOrderEvent) -> CanonicalOrderEvent:
        if self.session.get(CanonicalOrderEventModel, event.event_id) is None:
            values = asdict(event)
            values["metadata_json"] = values.pop("metadata")
            self.session.add(CanonicalOrderEventModel(**values))
            self.session.flush()
        return event

    def events(self, aggregate_id: str) -> tuple[CanonicalOrderEvent, ...]:
        rows = self.session.scalars(
            select(CanonicalOrderEventModel)
            .where(CanonicalOrderEventModel.aggregate_id == aggregate_id)
            .order_by(CanonicalOrderEventModel.aggregate_version)
        ).all()
        result = []
        for row in rows:
            values = {column.name: getattr(row, column.name) for column in row.__table__.columns}
            values["metadata"] = values.pop("metadata_json") or {}
            result.append(CanonicalOrderEvent(**values))
        return tuple(result)


class DatabasePaperExecutionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, execution_key: str) -> PaperExecutionRecord | None:
        model = self.session.get(PaperExecutionModel, execution_key)
        if model is None:
            return None
        fills = self.session.scalars(select(PaperFillModel).where(PaperFillModel.execution_key == execution_key)).all()
        return self._record(model, fills)

    def save(self, record: PaperExecutionRecord) -> PaperExecutionRecord:
        model = self.session.get(PaperExecutionModel, record.execution_key)
        values = asdict(record)
        fills = values.pop("fills")
        values["rejection_reasons_json"] = values.pop("rejection_reasons")
        values["warnings_json"] = values.pop("warnings")
        values["metadata_json"] = values.pop("metadata")
        if model is None:
            self.session.add(PaperExecutionModel(**values))
        else:
            for key, value in values.items():
                setattr(model, key, value)
        for fill in fills:
            if self.session.get(PaperFillModel, fill["fill_id"]) is None:
                fill["metadata_json"] = fill.pop("metadata")
                self.session.add(PaperFillModel(**fill))
        self.session.flush()
        return record

    def all(self) -> tuple[PaperExecutionRecord, ...]:
        rows = self.session.scalars(select(PaperExecutionModel).order_by(PaperExecutionModel.created_at)).all()
        return tuple(self.get(row.execution_key) for row in rows if row is not None)  # type: ignore[misc]

    @staticmethod
    def _record(model: PaperExecutionModel, fills: Iterable[PaperFillModel]) -> PaperExecutionRecord:
        fill_profiles = tuple(PaperFillProfile(
            fill_id=f.fill_id, execution_key=f.execution_key, aggregate_id=f.aggregate_id,
            client_order_id=f.client_order_id, leg_id=f.leg_id, symbol=f.symbol, side=f.side,
            quantity=f.quantity, fill_price=f.fill_price, reference_price=f.reference_price,
            slippage_amount=f.slippage_amount, slippage_bps=f.slippage_bps,
            commission=f.commission, latency_ms=f.latency_ms, filled_at=f.filled_at,
            metadata=f.metadata_json or {},
        ) for f in fills)
        return PaperExecutionRecord(
            execution_key=model.execution_key, session_id=model.session_id, cycle_id=model.cycle_id,
            aggregate_id=model.aggregate_id, client_order_id=model.client_order_id, account_id=model.account_id,
            order_type=model.order_type, time_in_force=model.time_in_force, status=model.status,
            requested_quantity=model.requested_quantity, filled_quantity=model.filled_quantity,
            remaining_quantity=model.remaining_quantity, average_fill_price=model.average_fill_price,
            gross_value=model.gross_value, commissions=model.commissions, net_cash_flow=model.net_cash_flow,
            latency_ms=model.latency_ms, fills=fill_profiles,
            rejection_reasons=tuple(model.rejection_reasons_json or []), warnings=tuple(model.warnings_json or []),
            created_at=model.created_at, updated_at=model.updated_at, metadata=model.metadata_json or {},
        )


class DatabasePaperPositionRepository:
    """Adapter making portfolio_positions authoritative for paper positions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, position_id: str) -> PaperPositionProfile | None:
        model = self.session.get(PortfolioPositionModel, position_id)
        return None if model is None else self._profile(model)

    def save(self, position: PaperPositionProfile) -> PaperPositionProfile:
        model = self.session.get(PortfolioPositionModel, position.position_id)
        metadata = dict(position.metadata)
        metadata.update({
            "paper_session_id": position.session_id, "aggregate_id": position.aggregate_id,
            "asset_class": position.asset_class, "multiplier": position.multiplier,
            "cost_basis": position.cost_basis, "market_value": position.market_value,
            "total_commissions": position.total_commissions,
            "lots": [asdict(lot) for lot in position.lots],
            "high_water_mark": position.high_water_mark, "low_water_mark": position.low_water_mark,
            "profit_target_pct": position.profit_target_pct, "stop_loss_pct": position.stop_loss_pct,
            "trailing_stop_pct": position.trailing_stop_pct, "adjustment_count": position.adjustment_count,
        })
        values = dict(
            position_id=position.position_id, portfolio_id=position.account_id, symbol=position.symbol,
            strategy_id=str(metadata.get("strategy_id", position.aggregate_id)),
            strategy_type=str(metadata.get("strategy_type", position.asset_class)), direction=position.side,
            status=position.state, quantity=int(position.quantity), entry_price=position.average_cost,
            current_price=position.market_price, capital_committed=position.cost_basis,
            maximum_loss=metadata.get("maximum_loss"), maximum_profit=metadata.get("maximum_profit"),
            realized_pnl=position.realized_pnl, unrealized_pnl=position.unrealized_pnl,
            opened_at=position.opened_at, updated_at=position.updated_at, closed_at=position.closed_at,
            sector=str(metadata.get("sector", "UNKNOWN")), industry=str(metadata.get("industry", "UNKNOWN")),
            correlation_group=str(metadata.get("correlation_group", "")),
            delta=float(metadata.get("delta", 0.0)), gamma=float(metadata.get("gamma", 0.0)),
            theta=float(metadata.get("theta", 0.0)), vega=float(metadata.get("vega", 0.0)),
            rho=float(metadata.get("rho", 0.0)), source_artifact=str(metadata.get("source_artifact", "paper_trading")),
            metadata_json=metadata,
        )
        if model is None:
            self.session.add(PortfolioPositionModel(**values))
        else:
            for key, value in values.items():
                setattr(model, key, value)
        self.session.flush()
        return position

    def all(self) -> tuple[PaperPositionProfile, ...]:
        rows = self.session.scalars(select(PortfolioPositionModel).order_by(PortfolioPositionModel.opened_at)).all()
        return tuple(self._profile(row) for row in rows)

    def open_for_session(self, session_id: str) -> tuple[PaperPositionProfile, ...]:
        return tuple(p for p in self.all() if p.session_id == session_id and p.is_open)

    @staticmethod
    def _profile(model: PortfolioPositionModel) -> PaperPositionProfile:
        md = model.metadata_json or {}
        lots = tuple(PaperPositionLot(**lot) for lot in md.get("lots", []))
        return PaperPositionProfile(
            position_id=model.position_id, session_id=str(md.get("paper_session_id", "")),
            account_id=model.portfolio_id, aggregate_id=str(md.get("aggregate_id", "")), symbol=model.symbol,
            asset_class=str(md.get("asset_class", model.strategy_type)), side=model.direction,
            quantity=float(model.quantity), average_cost=model.entry_price,
            multiplier=int(md.get("multiplier", 1)), market_price=model.current_price,
            market_value=float(md.get("market_value", model.current_price * model.quantity)),
            cost_basis=float(md.get("cost_basis", model.capital_committed)), realized_pnl=model.realized_pnl,
            unrealized_pnl=model.unrealized_pnl, total_commissions=float(md.get("total_commissions", 0.0)),
            state=model.status, lots=lots, high_water_mark=md.get("high_water_mark"),
            low_water_mark=md.get("low_water_mark"), profit_target_pct=md.get("profit_target_pct"),
            stop_loss_pct=md.get("stop_loss_pct"), trailing_stop_pct=md.get("trailing_stop_pct"),
            adjustment_count=int(md.get("adjustment_count", 0)), opened_at=model.opened_at,
            updated_at=model.updated_at, closed_at=model.closed_at, metadata=md,
        )

class DatabasePaperTradingRuntimeRepository:
    """Database replacement for JsonPaperTradingRuntimeRepository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, session_id: str):
        from trading_ai.paper_trading.paper_trading_profile import (
            PaperTradingCycleProfile,
            PaperTradingRuntimeState,
            PaperTradingSessionProfile,
        )
        model = self.session.get(PaperTradingSessionModel, session_id)
        if model is None:
            return None
        raw = dict(model.profile_json or {})
        session_raw = dict(raw.get("session", {}))
        session_raw["strategy_names"] = tuple(session_raw.get("strategy_names", ()))
        session_raw["symbols"] = tuple(session_raw.get("symbols", ()))
        session_profile = PaperTradingSessionProfile(**session_raw)
        cycle_raw = raw.get("last_cycle")
        if cycle_raw is not None:
            cycle_raw = dict(cycle_raw)
            cycle_raw["scanned_symbols"] = tuple(cycle_raw.get("scanned_symbols", ()))
            cycle_raw["errors"] = tuple(cycle_raw.get("errors", ()))
            raw["last_cycle"] = PaperTradingCycleProfile(**cycle_raw)
        raw["pending_order_ids"] = tuple(raw.get("pending_order_ids", ()))
        raw["active_position_ids"] = tuple(raw.get("active_position_ids", ()))
        raw["session"] = session_profile
        return PaperTradingRuntimeState(**raw)

    def require(self, session_id: str):
        state = self.get(session_id)
        if state is None:
            raise KeyError(f"Paper-trading session not found: {session_id}")
        return state

    def save(self, state):
        payload = asdict(state)
        profile = state.session
        model = self.session.get(PaperTradingSessionModel, profile.session_id)
        values = {
            "session_id": profile.session_id,
            "account_id": profile.account_id,
            "state": profile.state,
            "version": state.version,
            "started_at": profile.started_at or profile.created_at,
            "updated_at": state.updated_at,
            "stopped_at": profile.stopped_at,
            "profile_json": payload,
            "metadata_json": dict(state.metadata),
        }
        if model is None:
            self.session.add(PaperTradingSessionModel(**values))
        else:
            for key, value in values.items():
                setattr(model, key, value)
        self.session.flush()
        return state

    def all(self):
        rows = self.session.scalars(select(PaperTradingSessionModel).order_by(PaperTradingSessionModel.started_at)).all()
        return tuple(self.get(row.session_id) for row in rows)


class DatabasePaperAutomationRepository:
    """Database replacement for JsonPaperAutomationRepository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str):
        from trading_ai.paper_trading.paper_automation_profile import PaperAutomationCheckpoint
        model = self.session.get(PaperAutomationCheckpointModel, key)
        if model is None:
            return None
        payload = dict(model.payload_json or {})
        for key in ("completed_stages", "pending_stages", "candidate_ids", "order_draft_ids", "execution_keys", "position_ids"):
            payload[key] = tuple(payload.get(key, ()))
        return PaperAutomationCheckpoint(**payload)

    def save(self, checkpoint):
        payload = asdict(checkpoint)
        model = self.session.get(PaperAutomationCheckpointModel, checkpoint.checkpoint_id)
        values = {
            "checkpoint_id": checkpoint.checkpoint_id,
            "session_id": checkpoint.session_id,
            "cycle_id": checkpoint.cycle_id,
            "stage": checkpoint.stage,
            "status": checkpoint.state,
            "payload_json": payload,
            "created_at": checkpoint.created_at,
            "updated_at": checkpoint.updated_at,
        }
        if model is None:
            self.session.add(PaperAutomationCheckpointModel(**values))
        else:
            for key, value in values.items():
                setattr(model, key, value)
        self.session.flush()
        return checkpoint

    def all(self):
        rows = self.session.scalars(select(PaperAutomationCheckpointModel).order_by(PaperAutomationCheckpointModel.created_at)).all()
        return tuple(self.get(row.checkpoint_id) for row in rows)


class DatabaseTradingControlRepository:
    """Database replacement for JsonTradingControlRepository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, account_id: str):
        from trading_ai.risk_gateway.trading_control_profile import (
            KillSwitchProfile,
            TradingControlState,
            TradingHaltProfile,
        )
        model = self.session.get(PaperTradingControlModel, account_id)
        if model is None:
            return None
        payload = dict(model.metadata_json or {}).get("control_state")
        if payload:
            payload = dict(payload)
            payload["kill_switch"] = KillSwitchProfile(**payload["kill_switch"])
            payload["halts"] = tuple(TradingHaltProfile(**item) for item in payload.get("halts", ()))
            return TradingControlState(**payload)
        return TradingControlState(
            account_id=account_id,
            kill_switch=KillSwitchProfile(
                account_id=account_id,
                manual_active=model.trading_halted,
                reason=model.halt_reason,
                updated_at=model.updated_at,
            ),
            version=model.version,
            updated_at=model.updated_at,
        )

    def require(self, account_id: str):
        from trading_ai.risk_gateway.trading_control_profile import KillSwitchProfile, TradingControlState
        state = self.get(account_id)
        if state is None:
            state = TradingControlState(account_id=account_id, kill_switch=KillSwitchProfile(account_id=account_id))
            self.save(state)
        return state

    def save(self, state):
        payload = asdict(state)
        halted = state.kill_switch.active or any(h.active and not h.reduce_only for h in state.halts)
        reason = state.kill_switch.reason or next((h.reason for h in state.halts if h.active), None)
        model = self.session.get(PaperTradingControlModel, state.account_id)
        values = {
            "account_id": state.account_id,
            "entries_enabled": not halted,
            "exits_enabled": True,
            "trading_halted": halted,
            "halt_reason": reason,
            "version": state.version,
            "updated_at": state.updated_at,
            "metadata_json": {"control_state": payload},
        }
        if model is None:
            self.session.add(PaperTradingControlModel(**values))
        else:
            for key, value in values.items():
                setattr(model, key, value)
        self.session.flush()
        return state
