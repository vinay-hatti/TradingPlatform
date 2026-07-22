from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RiskMetric:
    name: str
    value: float
    limit: float
    utilization_pct: float
    status: str
    units: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RiskBreach:
    breach_id: str
    code: str
    severity: str
    status: str
    message: str
    metric: str
    observed_value: float
    limit_value: float
    position_ids: tuple[str, ...] = field(default_factory=tuple)
    recommended_action: str = "REVIEW"
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["position_ids"] = list(self.position_ids)
        return payload


@dataclass(frozen=True)
class StressScenarioResult:
    scenario_id: str
    name: str
    underlying_shock_pct: float
    volatility_shock_pct: float
    time_decay_days: int
    estimated_pnl: float
    estimated_loss_pct_nav: float
    status: str
    position_impacts: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["position_impacts"] = list(self.position_impacts)
        return payload


@dataclass(frozen=True)
class PortfolioRiskAssessment:
    assessment_id: str
    portfolio_id: str
    generated_at: str
    status: str
    trading_control: str
    net_liquidation_value: float
    cash_balance: float
    capital_committed: float
    open_position_count: int
    metrics: tuple[RiskMetric, ...]
    breaches: tuple[RiskBreach, ...]
    stress_results: tuple[StressScenarioResult, ...]
    aggregates: dict[str, Any]
    concentration: dict[str, Any]
    liquidity: dict[str, Any]
    recommendations: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    source_registry: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "portfolio_id": self.portfolio_id,
            "generated_at": self.generated_at,
            "status": self.status,
            "trading_control": self.trading_control,
            "net_liquidation_value": self.net_liquidation_value,
            "cash_balance": self.cash_balance,
            "capital_committed": self.capital_committed,
            "open_position_count": self.open_position_count,
            "metrics": [item.to_dict() for item in self.metrics],
            "breaches": [item.to_dict() for item in self.breaches],
            "stress_results": [item.to_dict() for item in self.stress_results],
            "aggregates": self.aggregates,
            "concentration": self.concentration,
            "liquidity": self.liquidity,
            "recommendations": list(self.recommendations),
            "warnings": list(self.warnings),
            "source_registry": self.source_registry,
        }
