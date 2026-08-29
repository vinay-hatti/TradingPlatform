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
    directional_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    signal_strength: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    inflection_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    input_quality: Mapped[float] = mapped_column(Float, nullable=False)
    disposition: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    horizon_min_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    horizon_max_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    semantic_state_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_as_of_date: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    option_snapshot_id: Mapped[str | None] = mapped_column(String(128), index=True)
    dealer_as_of_date: Mapped[str | None] = mapped_column(String(16), index=True)
    coverage_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    snapshot_timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class InflectionTimelineEventModel(Base):
    __tablename__ = "institutional_inflection_timeline_events"
    __table_args__ = (
        UniqueConstraint(
            "event_fingerprint",
            name="uq_m68_timeline_event_fingerprint",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    source_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    previous_transition_state: Mapped[str | None] = mapped_column(String(64), index=True)
    transition_state: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    transition_reason: Mapped[str] = mapped_column(String(128), nullable=False)
    directional_score: Mapped[float] = mapped_column(Float, nullable=False)
    signal_strength: Mapped[float] = mapped_column(Float, nullable=False)
    inflection_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_state_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
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
    authority_input_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    coverage_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_as_of_date: Mapped[str | None] = mapped_column(String(16), index=True)
    option_snapshot_id: Mapped[str | None] = mapped_column(String(128), index=True)
    published_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
