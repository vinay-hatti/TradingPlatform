from dataclasses import dataclass


@dataclass(frozen=True)
class WalkForwardIntegrationPolicy:
    enabled: bool = True
    require_valid_profile: bool = False
    reject_unapproved_profile: bool = False
    minimum_walk_forward_score: float = 40.0
    minimum_parameter_stability_score: float = 35.0
    maximum_degradation_pct: float = 0.50
    reject_critical_severity: bool = True

    def validate(self) -> None:
        for name in (
            "minimum_walk_forward_score",
            "minimum_parameter_stability_score",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100")
        if float(self.maximum_degradation_pct) < 0.0:
            raise ValueError("maximum_degradation_pct must be non-negative")
