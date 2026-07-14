from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionIntegrationPolicy:
    enabled: bool = True
    require_valid_execution_profile: bool = False
    reject_unapproved_execution: bool = False
    minimum_execution_score: float = 40.0
    minimum_routing_score: float = 40.0
    maximum_shortfall_bps: float = 100.0
    reject_critical_execution: bool = False

    def validate(self) -> None:
        for name in ("minimum_execution_score", "minimum_routing_score"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100")
        if self.maximum_shortfall_bps < 0:
            raise ValueError("maximum_shortfall_bps must be non-negative")
