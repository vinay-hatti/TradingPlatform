from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class RunKind(str, Enum):
    DATA_REFRESH = "DATA_REFRESH"
    DAILY_SCAN = "DAILY_SCAN"


class RefreshMode(str, Enum):
    CACHE_ONLY = "cache_only"
    REFRESH_MISSING = "refresh_missing"
    FORCE_FULL = "force_full"


class RunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class DataRefreshRequest(BaseModel):
    data_scope: Literal["underlying", "options", "all"] = "all"
    universe: str = "liquid-us-700"
    symbols: list[str] = Field(default_factory=list, max_length=1000)
    start: date = Field(default_factory=lambda: date.today() - timedelta(days=365))
    end: date = Field(default_factory=date.today)
    refresh_mode: RefreshMode = RefreshMode.REFRESH_MISSING
    minimum_bars: int = Field(default=20, ge=1, le=1000)
    stale_after_days: int = Field(default=1, ge=0, le=365)
    minimum_coverage_pct: float = Field(default=98.0, ge=0, le=100)
    maximum_failed_symbols: int = Field(default=10, ge=0, le=1000)
    continue_on_degraded_refresh: bool = True
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=2.0, ge=0, le=300)
    maximum_retry_backoff_seconds: float = Field(default=60.0, ge=0, le=900)
    retry_jitter_ratio: float = Field(default=0.20, ge=0, le=1)
    rate_limit_cooldown_seconds: float = Field(default=15.0, ge=0, le=900)
    circuit_breaker_threshold: int = Field(default=3, ge=1, le=100)
    circuit_breaker_cooldown_seconds: float = Field(default=30.0, ge=0, le=1800)
    batch_size: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start > self.end:
            raise ValueError("start cannot be after end")
        return self


class DailyScanRequest(BaseModel):
    universe: str = "liquid-us-700"
    symbols: list[str] = Field(default_factory=list, max_length=1000)
    start: date = Field(default_factory=lambda: date.today() - timedelta(days=365))
    end: date = Field(default_factory=date.today)
    minimum_score: float = Field(default=60.0, ge=0, le=100)
    top: int = Field(default=10, ge=1, le=100)
    pricing_dte: int = Field(default=30, ge=1, le=730)
    expiration_mode: Literal["automatic", "short", "swing", "medium", "long", "custom", "fixed"] = "automatic"
    minimum_dte: int = Field(default=14, ge=1, le=730)
    maximum_dte: int = Field(default=90, ge=1, le=730)
    maximum_expirations_per_symbol: int = Field(default=4, ge=1, le=12)
    maximum_trades_per_expiration: int = Field(default=3, ge=0, le=100)
    option_data_mode: Literal["live", "auto", "proxy"] = "live"
    liquidity_data_mode: Literal["adaptive", "strict"] = "adaptive"
    maximum_option_spread_pct: float = Field(default=0.25, ge=0, le=5)
    minimum_option_open_interest: int = Field(default=100, ge=0)
    minimum_option_volume: int = Field(default=10, ge=0)
    capital: float = Field(default=100000.0, gt=0)
    risk_per_trade_pct: float = Field(default=0.02, gt=0, le=1)
    max_position_pct: float = Field(default=0.05, gt=0, le=1)
    take_profit_pct: float = Field(default=0.30, gt=0, le=10)
    stop_loss_pct: float = Field(default=0.15, gt=0, le=1)
    refresh_mode: RefreshMode = RefreshMode.REFRESH_MISSING
    auto_refresh: bool = True
    minimum_refresh_coverage_pct: float = Field(default=98.0, ge=0, le=100)
    maximum_failed_refresh_symbols: int = Field(default=10, ge=0, le=1000)
    continue_on_degraded_refresh: bool = True
    refresh_max_retries: int = Field(default=3, ge=0, le=10)
    refresh_retry_backoff_seconds: float = Field(default=2.0, ge=0, le=300)
    refresh_maximum_retry_backoff_seconds: float = Field(default=60.0, ge=0, le=900)
    refresh_retry_jitter_ratio: float = Field(default=0.20, ge=0, le=1)
    refresh_rate_limit_cooldown_seconds: float = Field(default=15.0, ge=0, le=900)
    refresh_circuit_breaker_threshold: int = Field(default=3, ge=1, le=100)
    refresh_circuit_breaker_cooldown_seconds: float = Field(default=30.0, ge=0, le=1800)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start > self.end:
            raise ValueError("start cannot be after end")
        if self.minimum_dte > self.maximum_dte:
            raise ValueError("minimum_dte cannot exceed maximum_dte")
        return self


class ScannerRun(BaseModel):
    run_id: str
    kind: RunKind
    status: RunStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    requested_by: str
    request: dict[str, Any]
    command: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    report_date: str | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
