from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .profile import StressScenarioResult


@dataclass(frozen=True)
class StressScenario:
    scenario_id: str
    name: str
    underlying_shock_pct: float
    volatility_shock_pct: float
    time_decay_days: int


DEFAULT_SCENARIOS = (
    StressScenario("MARKET_DOWN_5", "Market down 5%", -5.0, 10.0, 1),
    StressScenario("MARKET_DOWN_10", "Market down 10%", -10.0, 20.0, 1),
    StressScenario("MARKET_UP_5", "Market up 5%", 5.0, -5.0, 1),
    StressScenario("VOLATILITY_SPIKE", "Volatility spike", -2.0, 40.0, 1),
    StressScenario("TIME_DECAY_7D", "Seven-day decay", 0.0, 0.0, 7),
)


class PortfolioStressService:
    def evaluate(self, positions: list[dict[str, Any]], nav: float, maximum_stress_loss_pct: float) -> tuple[StressScenarioResult, ...]:
        results: list[StressScenarioResult] = []
        safe_nav = nav if nav > 0 else 1.0
        for scenario in DEFAULT_SCENARIOS:
            impacts = []
            total = 0.0
            for position in positions:
                capital = float(position.get("capital_committed", 0.0) or 0.0)
                delta = float(position.get("delta", 0.0) or 0.0)
                gamma = float(position.get("gamma", 0.0) or 0.0)
                theta = float(position.get("theta", 0.0) or 0.0)
                vega = float(position.get("vega", 0.0) or 0.0)
                price_scale = max(capital, 100.0)
                move = scenario.underlying_shock_pct / 100.0
                vol_move = scenario.volatility_shock_pct / 100.0
                impact = (
                    delta * move * price_scale
                    + 0.5 * gamma * (move * price_scale) ** 2 / max(price_scale, 1.0)
                    + vega * vol_move
                    + theta * scenario.time_decay_days
                )
                maximum_loss = position.get("maximum_loss")
                if maximum_loss is not None:
                    impact = max(impact, -abs(float(maximum_loss)))
                impact = round(impact, 2)
                total += impact
                impacts.append({
                    "position_id": position.get("position_id", ""),
                    "symbol": position.get("symbol", ""),
                    "estimated_pnl": impact,
                })
            loss_pct = max(0.0, -total / safe_nav * 100.0)
            status = "BREACH" if loss_pct > maximum_stress_loss_pct else "PASS"
            results.append(StressScenarioResult(
                scenario_id=scenario.scenario_id,
                name=scenario.name,
                underlying_shock_pct=scenario.underlying_shock_pct,
                volatility_shock_pct=scenario.volatility_shock_pct,
                time_decay_days=scenario.time_decay_days,
                estimated_pnl=round(total, 2),
                estimated_loss_pct_nav=round(loss_pct, 4),
                status=status,
                position_impacts=tuple(impacts),
            ))
        return tuple(results)
