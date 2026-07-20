from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class TradeLegBlueprintProfile:
    symbol: str
    expiration: date
    option_type: str
    side: str
    strike: float
    quantity_ratio: int
    bid: float
    ask: float
    mark: float
    limit_price: float
    spread_pct: float
    open_interest: int
    volume: int
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None


@dataclass(frozen=True)
class StrategyBlueprintProfile:
    symbol: str
    strategy_name: str
    direction: str
    order_side: str
    order_type: str
    time_in_force: str
    legs: tuple[TradeLegBlueprintProfile, ...]
    net_limit_price: float
    net_credit_debit: float
    defined_risk: bool
    maximum_profit_per_contract: float | None
    maximum_loss_per_contract: float | None
    reward_risk_ratio: float
    probability_of_profit: float
    breakeven_points: tuple[float, ...] = ()


@dataclass(frozen=True)
class CapitalRequirementProfile:
    account_equity: float
    requested_risk_budget: float
    requested_buying_power_budget: float
    risk_per_contract: float
    buying_power_per_contract: float
    risk_limited_contracts: int
    buying_power_limited_contracts: int
    policy_limited_contracts: int
    recommended_contracts: int
    total_maximum_risk: float
    estimated_buying_power: float
    position_risk_pct: float
    buying_power_pct: float


@dataclass(frozen=True)
class TradeValidationCheckProfile:
    name: str
    passed: bool
    severity: str
    actual: str
    limit: str
    message: str


@dataclass(frozen=True)
class TradeTicketProfile:
    symbol: str
    strategy_name: str
    contracts: int
    order_type: str
    time_in_force: str
    net_limit_price: float
    estimated_entry_value: float
    maximum_profit: float | None
    maximum_loss: float | None
    estimated_buying_power: float
    legs: tuple[TradeLegBlueprintProfile, ...]
    ticket_status: str
    executable: bool


@dataclass(frozen=True)
class TradeConstructionProfile:
    blueprint: StrategyBlueprintProfile
    capital: CapitalRequirementProfile
    checks: tuple[TradeValidationCheckProfile, ...]
    ticket: TradeTicketProfile
    construction_score: float
    construction_grade: str
    risk_severity: str
    allowed: bool
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
