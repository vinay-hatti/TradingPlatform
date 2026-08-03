from __future__ import annotations

from sqlalchemy import Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from trading_ai.database.base import Base


class OpportunityModel(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        UniqueConstraint("scanner_run_id", "snapshot_id", "symbol", "strategy", name="uq_opportunity_source_identity"),
    )

    opportunity_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    scanner_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    snapshot_timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workflow_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class OpportunityAuditEventModel(Base):
    __tablename__ = "opportunity_audit_events"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "opportunity_version", name="uq_opportunity_audit_version"),
    )

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    opportunity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_state: Mapped[str | None] = mapped_column(String(32))
    new_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    event_timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
