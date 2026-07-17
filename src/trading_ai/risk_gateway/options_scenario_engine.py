from __future__ import annotations
from collections import defaultdict
from .options_risk_policy import OptionsRiskPolicy
from .options_risk_profile import (
    OptionGreekProfile, ScenarioResultProfile, ScenarioShockProfile,
)

def _direction(side: str) -> float:
    return -1.0 if side.upper().startswith("SELL") else 1.0

class OptionsScenarioEngine:
    def __init__(self, policy: OptionsRiskPolicy | None = None) -> None:
        self.policy = policy or OptionsRiskPolicy()
        self.policy.validate()

    def default_scenarios(self) -> tuple[ScenarioShockProfile, ...]:
        scenarios = []
        for shock in self.policy.scenario_underlying_shocks_pct:
            scenarios.append(ScenarioShockProfile(
                scenario_id=f"underlying_{shock:+.0%}",
                underlying_shock_pct=shock,
            ))
        for shock in self.policy.scenario_volatility_shocks:
            scenarios.append(ScenarioShockProfile(
                scenario_id=f"volatility_{shock:+.0%}",
                volatility_shock=shock,
            ))
        for days in self.policy.scenario_time_decay_days:
            scenarios.append(ScenarioShockProfile(
                scenario_id=f"time_decay_{days}d",
                time_decay_days=days,
            ))
        for underlying_shock in self.policy.scenario_underlying_shocks_pct:
            for vol_shock in self.policy.scenario_volatility_shocks:
                scenarios.append(ScenarioShockProfile(
                    scenario_id=f"combined_{underlying_shock:+.0%}_{vol_shock:+.0%}",
                    underlying_shock_pct=underlying_shock,
                    volatility_shock=vol_shock,
                ))
        return tuple(scenarios)

    def evaluate(
        self,
        legs: tuple[OptionGreekProfile, ...],
        scenarios: tuple[ScenarioShockProfile, ...] | None = None,
    ) -> tuple[ScenarioResultProfile, ...]:
        results = []
        for scenario in scenarios or self.default_scenarios():
            total_pnl = 0.0
            by_underlying = defaultdict(float)
            for leg in legs:
                underlying_price = float(leg.underlying_price or 0.0)
                d_s = underlying_price * float(scenario.underlying_shock_pct)
                d_vol = float(scenario.volatility_shock)
                days = float(scenario.time_decay_days)
                scale = _direction(leg.side) * abs(float(leg.quantity)) * max(int(leg.multiplier or 1), 1)

                delta_pnl = float(leg.delta) * d_s
                gamma_pnl = 0.5 * float(leg.gamma) * d_s * d_s
                vega_pnl = float(leg.vega) * d_vol
                theta_pnl = float(leg.theta) * days
                pnl = scale * (delta_pnl + gamma_pnl + vega_pnl + theta_pnl)
                total_pnl += pnl
                by_underlying[leg.underlying_symbol] += pnl

            results.append(ScenarioResultProfile(
                scenario_id=scenario.scenario_id,
                pnl=round(total_pnl, 6),
                loss=round(max(0.0, -total_pnl), 6),
                by_underlying={
                    key: round(value, 6)
                    for key, value in by_underlying.items()
                },
            ))
        return tuple(results)
