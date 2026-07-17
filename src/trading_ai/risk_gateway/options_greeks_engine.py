from __future__ import annotations
from collections import defaultdict
from .options_risk_policy import OptionsRiskPolicy
from .options_risk_profile import AggregatedGreeksProfile, OptionGreekProfile

def _direction(side: str) -> float:
    return -1.0 if side.upper().startswith("SELL") else 1.0

class OptionsGreeksEngine:
    def __init__(self, policy: OptionsRiskPolicy | None = None) -> None:
        self.policy = policy or OptionsRiskPolicy()
        self.policy.validate()

    def aggregate(self, legs: tuple[OptionGreekProfile, ...]) -> AggregatedGreeksProfile:
        totals = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}
        by_underlying = defaultdict(lambda: {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0})
        for leg in legs:
            scale = _direction(leg.side) * abs(float(leg.quantity)) * max(int(leg.multiplier or 1), 1)
            for greek in totals:
                contribution = float(getattr(leg, greek)) * scale
                totals[greek] += contribution
                by_underlying[leg.underlying_symbol][greek] += contribution
        return AggregatedGreeksProfile(
            delta=round(totals["delta"], 6),
            gamma=round(totals["gamma"], 6),
            vega=round(totals["vega"], 6),
            theta=round(totals["theta"], 6),
            rho=round(totals["rho"], 6),
            by_underlying={
                key: {name: round(value, 6) for name, value in values.items()}
                for key, values in by_underlying.items()
            },
        )
