from __future__ import annotations

from .walk_forward_governance_engine import WalkForwardGovernanceEngine
from .walk_forward_governance_policy import WalkForwardGovernancePolicy


class WalkForwardGovernanceService:
    def __init__(self, policy: WalkForwardGovernancePolicy | None = None, registry=None):
        self.policy = policy or WalkForwardGovernancePolicy()
        self.engine = WalkForwardGovernanceEngine(self.policy)
        self.registry = registry

    def evaluate(self, champion_profile, challenger_profile, champion_version="champion", challenger_version="challenger", challenger_parameters=None):
        profile = self.engine.evaluate(champion_profile, challenger_profile, champion_version, challenger_version)
        if profile.promotion_eligible and self.policy.automatic_promotion_enabled and self.registry is not None:
            if self.registry.get(challenger_version) is None:
                self.registry.register(challenger_version, challenger_parameters or {}, challenger_profile, activate=False, metadata={"governance": "challenger"})
            self.registry.activate(challenger_version)
            profile.promotion_applied = True
            profile.metadata["active_version"] = challenger_version
        return profile
