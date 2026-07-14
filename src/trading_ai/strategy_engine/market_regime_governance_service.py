from .market_regime_governance_engine import MarketRegimeGovernanceEngine
from .market_regime_governance_policy import MarketRegimeGovernancePolicy


class MarketRegimeGovernanceService:
    def __init__(self, policy: MarketRegimeGovernancePolicy | None = None, engine=None, registry=None):
        self.policy = policy or MarketRegimeGovernancePolicy()
        self.engine = engine or MarketRegimeGovernanceEngine(self.policy)
        self.registry = registry

    def evaluate(self, champion_metrics, challenger_metrics, drift_profile=None, champion_version="champion", challenger_version="challenger"):
        profile = self.engine.evaluate(champion_metrics, challenger_metrics, drift_profile, champion_version, challenger_version)
        if profile.promotion_eligible and self.policy.automatic_promotion_enabled and self.registry is not None:
            self.registry.promote(challenger_version, profile)
            profile.promotion_applied = True
        return profile
