from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from trading_ai.database.base import Base


class BrokerAccountBindingModel(Base):
    __tablename__ = "broker_account_bindings"
    __table_args__ = (UniqueConstraint("broker_name", "broker_account_id", name="uq_broker_account_binding"),)

    binding_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_environment: Mapped[str] = mapped_column(String(16), nullable=False)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    client_id: Mapped[int] = mapped_column(Integer, nullable=False)
    read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    live_trading_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class BrokerAccountSnapshotModel(Base):
    __tablename__ = "broker_account_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    binding_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    captured_at: Mapped[str] = mapped_column(String(64), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    net_liquidation: Mapped[float] = mapped_column(Float, nullable=False)
    total_cash_value: Mapped[float] = mapped_column(Float, nullable=False)
    available_funds: Mapped[float] = mapped_column(Float, nullable=False)
    buying_power: Mapped[float] = mapped_column(Float, nullable=False)
    excess_liquidity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class BrokerPositionSnapshotModel(Base):
    __tablename__ = "broker_position_snapshots"

    snapshot_position_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    account_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    contract_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    local_symbol: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    security_type: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    average_cost: Mapped[float] = mapped_column(Float, nullable=False)
    expiry: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    strike: Mapped[float | None] = mapped_column(Float)
    right: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    captured_at: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class BrokerReconciliationRunModel(Base):
    __tablename__ = "broker_reconciliation_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    binding_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    account_match: Mapped[bool] = mapped_column(Boolean, nullable=False)
    position_difference_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

class BrokerOrderModel(Base):
    __tablename__ = "broker_orders"
    __table_args__ = (
        UniqueConstraint("binding_id", "aggregate_id", name="uq_broker_order_binding_aggregate"),
        UniqueConstraint("binding_id", "broker_order_id", name="uq_broker_order_binding_order_id"),
    )
    broker_order_record_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    binding_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    client_order_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    permanent_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    api_client_id: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    security_type: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    time_in_force: Mapped[str] = mapped_column(String(16), nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Float)
    stop_price: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    filled_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    remaining_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    average_fill_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    submitted_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

class BrokerExecutionModel(Base):
    __tablename__ = "broker_executions"
    execution_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    broker_order_record_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    binding_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    permanent_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    contract_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    security_type: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    commission: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    exchange: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    executed_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    imported_at: Mapped[str] = mapped_column(String(64), nullable=False)
    settled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

class BrokerOrderControlModel(Base):
    __tablename__ = "broker_order_controls"
    portfolio_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    paper_order_submission_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    activation_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    activated_at: Mapped[str | None] = mapped_column(String(64))
    activated_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    disabled_at: Mapped[str | None] = mapped_column(String(64))
    disable_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
