from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TradingSessionRiskProfile:
    account_id: str
    session_id: str
    starting_equity: float
    peak_equity: float
    current_equity: float
    daily_realized_pnl: float
    daily_unrealized_pnl: float
    consecutive_losing_trades: int = 0
    rejected_orders: int = 0
    risk_breaches: int = 0
    as_of: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def daily_total_pnl(self) -> float:
        return self.daily_realized_pnl + self.daily_unrealized_pnl

    @property
    def intraday_drawdown(self) -> float:
        return max(0.0, self.peak_equity - self.current_equity)

    @property
    def drawdown_pct(self) -> float | None:
        if self.starting_equity <= 0:
            return None
        return self.intraday_drawdown / self.starting_equity


@dataclass(frozen=True)
class TradingHaltProfile:
    halt_id: str
    scope_type: str
    scope_value: str
    active: bool
    reason: str
    source: str
    reduce_only: bool = False
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    expires_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KillSwitchProfile:
    account_id: str
    manual_active: bool = False
    automatic_active: bool = False
    reason: str | None = None
    activated_by: str | None = None
    activated_at: str | None = None
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def active(self) -> bool:
        return self.manual_active or self.automatic_active


@dataclass(frozen=True)
class TradingControlState:
    account_id: str
    kill_switch: KillSwitchProfile
    halts: tuple[TradingHaltProfile, ...] = ()
    version: int = 1
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradingControlCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradingControlDecision:
    valid: bool
    allowed: bool
    account_id: str
    aggregate_id: str
    score: float
    grade: str
    severity: str
    recommendation: str
    reduce_only: bool
    session: TradingSessionRiskProfile | None = None
    control_state: TradingControlState | None = None
    checks: tuple[TradingControlCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CombinedRiskGatewayDecision:
    valid: bool
    allowed: bool
    aggregate_id: str
    client_order_id: str
    account_id: str
    score: float
    grade: str
    severity: str
    recommendation: str
    order_level_decision: Any = None
    portfolio_decision: Any = None
    options_decision: Any = None
    trading_control_decision: TradingControlDecision | None = None
    rejection_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
