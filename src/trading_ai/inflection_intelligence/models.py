from __future__ import annotations

from sqlalchemy import Float, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from trading_ai.database.base import Base


class InflectionSnapshotModel(Base):
    __tablename__ = "institutional_inflection_snapshots"
    __table_args__ = (
        UniqueConstraint("publication_name", "source_run_id", "symbol", "timeframe", name="uq_m68_inflection_lineage"),
    )

    snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    publication_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    transition_state: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    inflection_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    horizon_min_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    horizon_max_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    state_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    snapshot_timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class InflectionTimelineEventModel(Base):
    __tablename__ = "institutional_inflection_timeline_events"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "state_hash", name="uq_m68_timeline_state"),
    )

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    transition_state: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    inflection_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    state_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class InflectionPublicationModel(Base):
    __tablename__ = "institutional_inflection_publications"

    publication_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    publication_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    source_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    symbol_count: Mapped[int] = mapped_column(Integer, nullable=False)
    high_conviction_count: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
