from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from trading_ai.database.base import Base


class BrokerCurrentPositionModel(Base):
    __tablename__ = "broker_current_positions"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "broker_account_id", "contract_id",
            name="uq_m63_current_broker_position",
        ),
    )

    broker_position_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    binding_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    contract_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    local_symbol: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    security_type: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    signed_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    average_cost: Mapped[float] = mapped_column(Float, nullable=False)
    market_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    market_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expiry: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    strike: Mapped[float | None] = mapped_column(Float)
    right: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False, default="BROKER_DISCOVERED", index=True)
    reconciliation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="MATCHED", index=True)
    portfolio_position_id: Mapped[str | None] = mapped_column(String(128), index=True)
    managed_position_id: Mapped[str | None] = mapped_column(String(128), index=True)
    first_seen_at: Mapped[str] = mapped_column(String(64), nullable=False)
    last_seen_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    closed_at: Mapped[str | None] = mapped_column(String(64))
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class BrokerPortfolioPublicationModel(Base):
    __tablename__ = "broker_portfolio_publications"

    publication_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    publication_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    reconciliation_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    position_count: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    broker_discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    drift_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class BrokerPortfolioAlertModel(Base):
    __tablename__ = "broker_portfolio_alerts"
    alert_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_position_id: Mapped[str | None] = mapped_column(String(160), index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resolved_at: Mapped[str | None] = mapped_column(String(64))
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
