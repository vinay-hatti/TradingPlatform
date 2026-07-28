from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from trading_ai.database.base import Base


class CanonicalOrderModel(Base):
    __tablename__ = "canonical_orders"

    aggregate_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    order_type: Mapped[str] = mapped_column(String(32), nullable=False)
    time_in_force: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    total_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    filled_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    remaining_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    average_fill_price: Mapped[float | None] = mapped_column(Float)
    limit_price: Mapped[float | None] = mapped_column(Float)
    stop_price: Mapped[float | None] = mapped_column(Float)
    outside_regular_hours: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    strategy_name: Mapped[str | None] = mapped_column(String(128))
    broker_order_id: Mapped[str | None] = mapped_column(String(128), index=True)
    parent_aggregate_id: Mapped[str | None] = mapped_column(String(128), index=True)
    root_aggregate_id: Mapped[str | None] = mapped_column(String(128), index=True)
    replace_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    legs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    terminal_at: Mapped[str | None] = mapped_column(String(64))
    last_event_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class CanonicalOrderEventModel(Base):
    __tablename__ = "canonical_order_events"
    __table_args__ = (
        UniqueConstraint("aggregate_id", "aggregate_version", name="uq_canonical_order_event_version"),
    )

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    client_order_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_state: Mapped[str] = mapped_column(String(32), nullable=False)
    new_state: Mapped[str] = mapped_column(String(32), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(128))
    filled_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    remaining_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    average_fill_price: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String(128), index=True)
    causation_id: Mapped[str | None] = mapped_column(String(128), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PaperExecutionModel(Base):
    __tablename__ = "paper_executions"

    execution_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    cycle_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    client_order_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    order_type: Mapped[str] = mapped_column(String(32), nullable=False)
    time_in_force: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    requested_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    filled_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    average_fill_price: Mapped[float | None] = mapped_column(Float)
    gross_value: Mapped[float] = mapped_column(Float, nullable=False)
    commissions: Mapped[float] = mapped_column(Float, nullable=False)
    net_cash_flow: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    rejection_reasons_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PaperFillModel(Base):
    __tablename__ = "paper_fills"

    fill_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    execution_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    client_order_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    leg_id: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    fill_price: Mapped[float] = mapped_column(Float, nullable=False)
    reference_price: Mapped[float] = mapped_column(Float, nullable=False)
    slippage_amount: Mapped[float] = mapped_column(Float, nullable=False)
    slippage_bps: Mapped[float] = mapped_column(Float, nullable=False)
    commission: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PortfolioCashReservationModel(Base):
    __tablename__ = "portfolio_cash_reservations"

    reservation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    reserved_at: Mapped[str] = mapped_column(String(64), nullable=False)
    released_at: Mapped[str | None] = mapped_column(String(64))
    release_reason: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PaperTradingSessionModel(Base):
    __tablename__ = "paper_trading_sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    stopped_at: Mapped[str | None] = mapped_column(String(64))
    profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PaperAutomationCheckpointModel(Base):
    __tablename__ = "paper_automation_checkpoints"
    __table_args__ = (
        UniqueConstraint("session_id", "cycle_id", "stage", name="uq_paper_checkpoint_stage"),
    )

    checkpoint_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    cycle_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class PaperTradingControlModel(Base):
    __tablename__ = "paper_trading_controls"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entries_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    exits_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trading_halted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    halt_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PaperPositionMarkModel(Base):
    __tablename__ = "paper_position_marks"

    mark_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    position_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mark_price: Mapped[float] = mapped_column(Float, nullable=False)
    market_value: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    marked_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PaperPositionLifecycleEventModel(Base):
    __tablename__ = "paper_position_lifecycle_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    position_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    occurred_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reference_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
