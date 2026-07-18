from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


HealthStatus = Literal["healthy", "degraded", "offline", "unknown"]
Severity = Literal["normal", "positive", "warning", "critical"]
Trend = Literal["up", "down", "flat", "unknown"]


class MetricCard(BaseModel):
    key: str
    label: str
    value: str
    detail: str | None = None
    trend: Trend = "unknown"
    severity: Severity = "normal"
    source: str | None = None
    as_of: datetime | None = None


class OpportunitySummary(BaseModel):
    symbol: str
    direction: Literal["CALL", "PUT", "WATCH"]
    score: float = Field(ge=0, le=100)
    probability_of_profit: float | None = Field(default=None, ge=0, le=1)
    regime: str
    contract: str | None = None
    expected_value: float | None = None
    liquidity_score: float | None = Field(default=None, ge=0, le=100)
    source: str | None = None


class SystemComponentHealth(BaseModel):
    name: str
    status: HealthStatus
    detail: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    as_of: datetime | None = None
    source: str | None = None


class DashboardSourceStatus(BaseModel):
    source: str
    status: HealthStatus
    detail: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    records: int | None = Field(default=None, ge=0)
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DashboardSnapshot(BaseModel):
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    environment: str
    market_status: str
    market_regime: str
    risk_mode: str
    ai_confidence: float = Field(ge=0, le=1)
    metrics: list[MetricCard]
    opportunities: list[OpportunitySummary]
    system_health: list[SystemComponentHealth]
    sources: list[DashboardSourceStatus] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
