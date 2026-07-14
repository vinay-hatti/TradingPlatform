from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionFill:
    order_id: str = ""
    symbol: str = ""
    side: str = "BUY"
    quantity_requested: float = 0.0
    quantity_filled: float = 0.0
    decision_price: float = 0.0
    arrival_price: float = 0.0
    fill_price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    submitted_at: Any = None
    filled_at: Any = None
    venue: str = "UNKNOWN"
    commission: float = 0.0
    fees: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionAnalyticsProfile:
    symbol: str = ""
    strategy: str = ""
    order_count: int = 0
    requested_quantity: float = 0.0
    filled_quantity: float = 0.0
    fill_ratio: float = 0.0
    decision_price: float = 0.0
    arrival_price: float = 0.0
    average_fill_price: float = 0.0
    average_bid: float = 0.0
    average_ask: float = 0.0
    quoted_spread: float = 0.0
    quoted_spread_pct: float = 0.0
    effective_spread: float = 0.0
    effective_spread_bps: float = 0.0
    implementation_shortfall: float = 0.0
    implementation_shortfall_bps: float = 0.0
    arrival_slippage: float = 0.0
    arrival_slippage_bps: float = 0.0
    market_impact: float = 0.0
    market_impact_bps: float = 0.0
    timing_cost: float = 0.0
    timing_cost_bps: float = 0.0
    total_commission: float = 0.0
    total_fees: float = 0.0
    fill_delay_seconds: float = 0.0
    slippage_score: float = 0.0
    spread_score: float = 0.0
    impact_score: float = 0.0
    fill_quality_score: float = 0.0
    latency_score: float = 0.0
    execution_score: float = 0.0
    execution_grade: str = "N/A"
    execution_severity: str = "UNKNOWN"
    allowed: bool = True
    valid: bool = False
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    fills: tuple[ExecutionFill, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
