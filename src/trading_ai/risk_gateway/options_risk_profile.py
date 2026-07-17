from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from .pretrade_risk_profile import PreTradeAccountProfile, PreTradeRiskRequest

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class OptionGreekProfile:
    leg_id: str
    symbol: str
    underlying_symbol: str
    quantity: float
    multiplier: int
    side: str
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    implied_volatility: float | None = None
    underlying_price: float | None = None
    option_price: float | None = None
    strike: float | None = None
    expiration: str | None = None
    option_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class AggregatedGreeksProfile:
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    by_underlying: dict[str, dict[str, float]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ScenarioShockProfile:
    scenario_id: str
    underlying_shock_pct: float = 0.0
    volatility_shock: float = 0.0
    time_decay_days: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ScenarioResultProfile:
    scenario_id: str
    pnl: float
    loss: float
    by_underlying: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class StrategyMarginProfile:
    strategy_classification: str
    defined_risk: bool
    uncovered_short_option: bool
    maximum_loss: float | None
    margin_required: float
    margin_utilization: float | None
    width: float | None = None
    net_premium: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class OptionsRiskCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class OptionsRiskDecision:
    valid: bool
    allowed: bool
    aggregate_id: str
    client_order_id: str
    account_id: str
    score: float
    grade: str
    severity: str
    recommendation: str
    greeks: AggregatedGreeksProfile | None = None
    scenarios: tuple[ScenarioResultProfile, ...] = ()
    worst_scenario: ScenarioResultProfile | None = None
    margin: StrategyMarginProfile | None = None
    account: PreTradeAccountProfile | None = None
    order: PreTradeRiskRequest | None = None
    checks: tuple[OptionsRiskCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
