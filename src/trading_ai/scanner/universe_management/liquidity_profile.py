from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class LiquidityMetrics:
    symbol: str
    as_of: datetime
    price: float | None = None
    average_daily_volume: int | None = None
    average_daily_dollar_volume: float | None = None
    bid_ask_spread_pct: float | None = None
    market_cap: float | None = None
    option_volume: int | None = None
    option_open_interest: int | None = None
    halted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiquidityEvaluation:
    symbol: str
    status: str
    eligible: bool
    liquidity_score: float
    rejection_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    metrics: LiquidityMetrics | None
    security: dict[str, Any]


@dataclass(frozen=True)
class LiquidityScreenResult:
    generated_at: datetime
    status: str
    evaluated_count: int
    eligible_count: int
    rejected_count: int
    review_count: int
    missing_metrics_count: int
    stale_metrics_count: int
    evaluations: tuple[LiquidityEvaluation, ...]
    rejection_breakdown: dict[str, int]
    artifacts: dict[str, str]
