from __future__ import annotations

from typing import Any, Iterable

from trading_ai.strategy_engine.portfolio_optimization_engine import (
    PortfolioOptimizationEngine,
)
from trading_ai.strategy_engine.portfolio_optimization_policy import (
    PortfolioOptimizationPolicy,
)
from trading_ai.strategy_engine.portfolio_optimization_profile import (
    PortfolioOptimizationCandidate,
)


class PortfolioOptimizationService:
    def __init__(self, policy: PortfolioOptimizationPolicy | None = None, engine: PortfolioOptimizationEngine | None = None):
        self.policy = policy or PortfolioOptimizationPolicy()
        self.engine = engine or PortfolioOptimizationEngine(self.policy)

    def optimize(self, candidates: Iterable[Any], initial_capital: float):
        normalized = [self._normalize(item, index) for index, item in enumerate(candidates)]
        return self.engine.optimize(normalized, initial_capital)

    def _normalize(self, item: Any, index: int) -> PortfolioOptimizationCandidate:
        def value(name, default=None):
            if isinstance(item, dict):
                return item.get(name, default)
            return getattr(item, name, default)

        risk_surface = value("risk_surface_profile", None)
        if risk_surface is None:
            metadata = value("metadata", {}) or {}
            if isinstance(metadata, dict):
                risk_surface = metadata.get("risk_surface_profile")

        def surface_value(name, default):
            if risk_surface is None:
                return value(name, default)
            if isinstance(risk_surface, dict):
                return risk_surface.get(name, value(name, default))
            return getattr(risk_surface, name, value(name, default))

        candidate_id = value("decision_id", None) or value("position_id", None) or value("candidate_id", None) or f"CANDIDATE_{index + 1}"
        capital_required = float(value("capital_required", value("allocation_dollars", 0.0)) or 0.0)
        expected_profit = float(value("expected_profit", 0.0) or 0.0)
        expected_return = value("expected_return_pct", None)
        if expected_return is None:
            expected_return = expected_profit / capital_required if capital_required else 0.0
        return PortfolioOptimizationCandidate(
            candidate_id=str(candidate_id), symbol=str(value("symbol", "UNKNOWN") or "UNKNOWN").upper(),
            strategy=str(value("strategy", "UNKNOWN") or "UNKNOWN").upper(),
            sector=str(value("sector", "UNKNOWN") or "UNKNOWN").upper(),
            correlation_group=str(value("correlation_group", "UNKNOWN") or "UNKNOWN").upper(),
            capital_required=capital_required,
            maximum_loss=float(value("maximum_loss", 0.0) or 0.0),
            expected_profit=expected_profit,
            expected_return_pct=float(expected_return or 0.0),
            ranking_score=float(value("ranking_score", 0.0) or 0.0),
            strategy_score=float(value("strategy_score", 0.0) or 0.0),
            surface_score=float(surface_value("surface_score", 50.0) or 0.0),
            surface_severity=str(surface_value("risk_severity", "UNKNOWN") or "UNKNOWN").upper(),
            allowed=bool(value("allowed", True)) and bool(surface_value("allowed", True)),
            delta=float(value("net_delta", value("delta", 0.0)) or 0.0),
            gamma=float(value("net_gamma", value("gamma", 0.0)) or 0.0),
            theta=float(value("net_theta", value("theta", 0.0)) or 0.0),
            vega=float(value("net_vega", value("vega", 0.0)) or 0.0),
            rho=float(value("net_rho", value("rho", 0.0)) or 0.0),
            metadata=dict(value("metadata", {}) or {}), source=item,
        )
