from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from trading_ai.database.base import Base

class MarketOverviewSnapshotModel(Base):
    __tablename__ = "market_overview_snapshot"
    snapshot_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    market_bias: Mapped[str] = mapped_column(String(32), nullable=False)
    preferred_strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    market_health_score: Mapped[float] = mapped_column(Float, nullable=False)
    trend_score: Mapped[float] = mapped_column(Float, nullable=False)
    momentum_score: Mapped[float] = mapped_column(Float, nullable=False)
    breadth_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_on_score: Mapped[float] = mapped_column(Float, nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    trend_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    volatility_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    breadth_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    liquidity_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    regime_transition_risk: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

class MarketBreadthSnapshotModel(Base):
    __tablename__ = "market_breadth_snapshot"
    snapshot_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    universe_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    evaluated_symbols: Mapped[int] = mapped_column(Integer, nullable=False)
    advancers: Mapped[int] = mapped_column(Integer, nullable=False)
    decliners: Mapped[int] = mapped_column(Integer, nullable=False)
    unchanged: Mapped[int] = mapped_column(Integer, nullable=False)
    pct_above_ema20: Mapped[float] = mapped_column(Float, nullable=False)
    pct_above_sma50: Mapped[float] = mapped_column(Float, nullable=False)
    pct_above_sma200: Mapped[float] = mapped_column(Float, nullable=False)
    new_highs_20d: Mapped[int] = mapped_column(Integer, nullable=False)
    new_lows_20d: Mapped[int] = mapped_column(Integer, nullable=False)
    up_volume: Mapped[float] = mapped_column(Float, nullable=False)
    down_volume: Mapped[float] = mapped_column(Float, nullable=False)
    breadth_score: Mapped[float] = mapped_column(Float, nullable=False)
    breadth_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

class SectorRotationSnapshotModel(Base):
    __tablename__ = "sector_rotation_snapshot"
    snapshot_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    sector_etf: Mapped[str] = mapped_column(String(16), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sector: Mapped[str] = mapped_column(String(64), nullable=False)
    return_1d: Mapped[float] = mapped_column(Float, nullable=False)
    return_5d: Mapped[float] = mapped_column(Float, nullable=False)
    return_20d: Mapped[float] = mapped_column(Float, nullable=False)
    relative_strength: Mapped[float] = mapped_column(Float, nullable=False)
    trend_score: Mapped[float] = mapped_column(Float, nullable=False)
    momentum_score: Mapped[float] = mapped_column(Float, nullable=False)
    dealer_positioning_score: Mapped[float | None] = mapped_column(Float)
    rotation_label: Mapped[str] = mapped_column(String(24), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
