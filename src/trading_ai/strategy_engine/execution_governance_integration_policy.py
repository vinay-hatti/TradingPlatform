from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionGovernanceIntegrationPolicy:
    enabled: bool = True
    require_valid_governance_profile: bool = False
    reject_unapproved_governance: bool = True
    reject_severe_governance: bool = True
    minimum_governance_score: float = 60.0
    require_route_registry: bool = False
    require_champion_route: bool = False
    allow_missing_champion_challenger: bool = True

    def validate(self):
        if not 0.0 <= float(self.minimum_governance_score) <= 100.0:
            raise ValueError("minimum_governance_score must be between 0 and 100")
        return self
