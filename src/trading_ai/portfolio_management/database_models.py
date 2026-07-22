from __future__ import annotations

from sqlalchemy import Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from trading_ai.database.base import Base


class PortfolioAccountModel(Base):
    __tablename__ = "portfolio_accounts"

    portfolio_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PortfolioPositionModel(Base):
    __tablename__ = "portfolio_positions"
    __table_args__ = (UniqueConstraint("portfolio_id", "position_id", name="uq_portfolio_position"),)

    position_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    strategy_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    strategy_type: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    capital_committed: Mapped[float] = mapped_column(Float, nullable=False)
    maximum_loss: Mapped[float | None] = mapped_column(Float)
    maximum_profit: Mapped[float | None] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    opened_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    closed_at: Mapped[str | None] = mapped_column(String(64))
    sector: Mapped[str] = mapped_column(String(128), nullable=False, default="UNKNOWN")
    industry: Mapped[str] = mapped_column(String(128), nullable=False, default="UNKNOWN")
    correlation_group: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gamma: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    theta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    vega: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rho: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_artifact: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PortfolioCashLedgerModel(Base):
    __tablename__ = "portfolio_cash_ledger"

    entry_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    occurred_at: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class PortfolioSnapshotModel(Base):
    __tablename__ = "portfolio_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    generated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    registry_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    registry_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    exposure_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class PortfolioAuditModel(Base):
    __tablename__ = "portfolio_audit_history"

    audit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[str] = mapped_column(String(64), nullable=False)
    registry_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    open_position_count: Mapped[int] = mapped_column(Integer, nullable=False)
    closed_position_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cash_balance: Mapped[float] = mapped_column(Float, nullable=False)
    net_liquidation_value: Mapped[float] = mapped_column(Float, nullable=False)
    capital_committed: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    source_registry: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PortfolioSyncRunModel(Base):
    __tablename__ = "portfolio_sync_runs"

    sync_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    registry_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    accounts_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    positions_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ledger_entries_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshots_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    audit_records_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
