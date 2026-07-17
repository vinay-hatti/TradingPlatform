from __future__ import annotations
from .options_risk_engine import OptionsRiskEngine
from .options_risk_policy import OptionsRiskPolicy
from .options_risk_profile import (
    OptionGreekProfile, OptionsRiskDecision, ScenarioShockProfile,
)
from .pretrade_risk_profile import PreTradeAccountProfile, PreTradeRiskRequest

class OptionsRiskService:
    def __init__(self, policy: OptionsRiskPolicy | None = None) -> None:
        self.engine = OptionsRiskEngine(policy)

    def evaluate(
        self,
        order: PreTradeRiskRequest,
        account: PreTradeAccountProfile | None,
        greek_legs: tuple[OptionGreekProfile, ...],
        scenarios: tuple[ScenarioShockProfile, ...] | None = None,
    ) -> OptionsRiskDecision:
        return self.engine.evaluate(order, account, greek_legs, scenarios)
