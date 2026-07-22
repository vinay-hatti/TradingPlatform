from __future__ import annotations

import hashlib
from typing import Any

from .policy import PortfolioRiskPolicy
from .profile import RiskBreach, RiskMetric, StressScenarioResult, utc_now_iso


class PortfolioRiskBreachService:
    def evaluate(self, exposure: dict[str, Any], stress_results: tuple[StressScenarioResult, ...], policy: PortfolioRiskPolicy) -> tuple[tuple[RiskMetric, ...], tuple[RiskBreach, ...], str, str, tuple[str, ...]]:
        metric_specs = [
            ("capital_utilization_pct", exposure["capital_utilization_pct"], policy.maximum_capital_utilization_pct, "%", False),
            ("cash_reserve_pct", exposure["cash_reserve_pct"], policy.minimum_cash_reserve_pct, "%", True),
            ("symbol_concentration_pct", exposure["concentration"].get("largest_symbol_pct", 0.0), policy.maximum_symbol_concentration_pct, "%", False),
            ("sector_concentration_pct", exposure["concentration"].get("largest_sector_pct", 0.0), policy.maximum_sector_concentration_pct, "%", False),
            ("strategy_concentration_pct", exposure["concentration"].get("largest_strategy_pct", 0.0), policy.maximum_strategy_concentration_pct, "%", False),
            ("direction_concentration_pct", exposure["concentration"].get("largest_direction_pct", 0.0), policy.maximum_direction_concentration_pct, "%", False),
            ("correlation_group_pct", exposure["concentration"].get("largest_correlation_group_pct", 0.0), policy.maximum_correlation_group_pct, "%", False),
            ("maximum_loss_pct_nav", exposure["aggregates"].get("maximum_loss", 0.0) / max(exposure["nav"], 1.0) * 100.0, policy.maximum_portfolio_loss_pct, "%", False),
            ("delta_abs", abs(exposure["aggregates"].get("delta", 0.0)), policy.maximum_delta_abs, "delta", False),
            ("gamma_abs", abs(exposure["aggregates"].get("gamma", 0.0)), policy.maximum_gamma_abs, "gamma", False),
            ("theta_abs", abs(exposure["aggregates"].get("theta", 0.0)), policy.maximum_theta_abs, "theta", False),
            ("vega_abs", abs(exposure["aggregates"].get("vega", 0.0)), policy.maximum_vega_abs, "vega", False),
            ("rho_abs", abs(exposure["aggregates"].get("rho", 0.0)), policy.maximum_rho_abs, "rho", False),
            ("illiquid_capital_pct", exposure["liquidity"].get("illiquid_capital_pct", 0.0), policy.maximum_illiquid_capital_pct, "%", False),
        ]
        metrics: list[RiskMetric] = []
        breaches: list[RiskBreach] = []
        now = utc_now_iso()
        for name, value, limit, units, minimum_rule in metric_specs:
            utilization = (limit / value * 100.0) if minimum_rule and value > 0 else (value / limit * 100.0 if limit > 0 else 0.0)
            breached = value < limit if minimum_rule else value > limit
            status = "BREACH" if breached else ("WARNING" if utilization >= policy.warning_utilization_pct else "PASS")
            metrics.append(RiskMetric(name, round(value, 4), round(limit, 4), round(utilization, 4), status, units))
            if breached:
                severity = self._severity(utilization)
                breaches.append(self._breach(name, value, limit, severity, now))

        for result in stress_results:
            if result.status == "BREACH":
                utilization = result.estimated_loss_pct_nav / max(policy.maximum_stress_loss_pct, 0.0001) * 100.0
                breaches.append(self._breach(
                    f"stress_{result.scenario_id.lower()}",
                    result.estimated_loss_pct_nav,
                    policy.maximum_stress_loss_pct,
                    self._severity(utilization),
                    now,
                ))

        severities = {item.severity for item in breaches}
        if "CRITICAL" in severities:
            status = "CRITICAL"
            trading_control = "BLOCK_NEW_RISK" if policy.block_on_critical_breach else "REDUCE_ONLY"
        elif "HIGH" in severities:
            status = "HIGH_RISK"
            trading_control = "REDUCE_ONLY" if policy.reduce_only_on_high_breach else "REVIEW_REQUIRED"
        elif breaches:
            status = "BREACH"
            trading_control = "REVIEW_REQUIRED"
        elif any(item.status == "WARNING" for item in metrics):
            status = "WARNING"
            trading_control = "ALLOW_WITH_WARNING"
        else:
            status = "PASS"
            trading_control = "ALLOW"

        recommendations = tuple(dict.fromkeys(item.recommended_action for item in breaches))
        return tuple(metrics), tuple(breaches), status, trading_control, recommendations

    @staticmethod
    def _severity(utilization: float) -> str:
        if utilization >= 150.0:
            return "CRITICAL"
        if utilization >= 120.0:
            return "HIGH"
        return "MEDIUM"

    @staticmethod
    def _breach(name: str, value: float, limit: float, severity: str, now: str) -> RiskBreach:
        action_map = {
            "capital_utilization_pct": "REDUCE_CAPITAL_EXPOSURE",
            "cash_reserve_pct": "RESTORE_CASH_RESERVE",
            "symbol_concentration_pct": "REDUCE_SYMBOL_CONCENTRATION",
            "sector_concentration_pct": "REDUCE_SECTOR_CONCENTRATION",
            "strategy_concentration_pct": "DIVERSIFY_STRATEGIES",
            "direction_concentration_pct": "HEDGE_DIRECTIONAL_EXPOSURE",
            "correlation_group_pct": "REDUCE_CORRELATED_EXPOSURE",
            "maximum_loss_pct_nav": "REDUCE_DEFINED_MAXIMUM_LOSS",
            "delta_abs": "HEDGE_DELTA",
            "gamma_abs": "REDUCE_GAMMA",
            "theta_abs": "REDUCE_THETA_DECAY",
            "vega_abs": "HEDGE_VOLATILITY_EXPOSURE",
            "rho_abs": "REDUCE_RATE_EXPOSURE",
            "illiquid_capital_pct": "IMPROVE_LIQUIDITY",
        }
        action = action_map.get(name, "REDUCE_STRESS_EXPOSURE" if name.startswith("stress_") else "REVIEW")
        digest = hashlib.sha256(f"{name}|{value:.8f}|{limit:.8f}|{now[:19]}".encode()).hexdigest()[:16].upper()
        return RiskBreach(
            breach_id=f"RISK-{digest}", code=name.upper(), severity=severity, status="OPEN",
            message=f"{name} observed {value:.4f} versus limit {limit:.4f}", metric=name,
            observed_value=round(value, 4), limit_value=round(limit, 4), recommended_action=action,
            created_at=now,
        )
