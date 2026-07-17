from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionGovernanceIntegrationProfile:
    valid: bool = False
    allowed: bool = True
    governance_available: bool = False
    governance_score: float = 0.0
    governance_grade: str = "N/A"
    governance_severity: str = "UNKNOWN"
    aggregate_psi: float = 0.0
    maximum_metric_psi: float = 0.0
    deteriorated_metric_count: int = 0
    governance_recommendation: str = "UNAVAILABLE"
    route_registry_available: bool = False
    route_count: int = 0
    active_route_version: str = "UNAVAILABLE"
    champion_route_version: str = "UNAVAILABLE"
    challenger_route_versions: tuple[str, ...] = ()
    champion_challenger_available: bool = False
    challenger_version: str = "UNAVAILABLE"
    challenger_evaluation_score: float = 0.0
    challenger_recommendation: str = "UNAVAILABLE"
    route_promotion_recommended: bool = False
    execution_governance_profile: Any = None
    execution_route_registry_profile: Any = None
    execution_champion_challenger_profile: Any = None
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
