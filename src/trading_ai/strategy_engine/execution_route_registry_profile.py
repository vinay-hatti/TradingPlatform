from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionRouteVersionProfile:
    version: str = "UNAVAILABLE"
    route_type: str = "VENUE"
    route_name: str = "UNKNOWN"
    status: str = "REGISTERED"
    observation_count: int = 0
    route_score: float = 0.0
    confidence_score: float = 0.0
    average_shortfall_bps: float = 0.0
    average_fill_ratio: float = 0.0
    average_latency_seconds: float = 0.0
    average_spread_bps: float = 0.0
    governance_score: float = 0.0
    governance_grade: str = "N/A"
    governance_severity: str = "UNKNOWN"
    governance_allowed: bool = True
    active: bool = False
    champion: bool = False
    challenger: bool = False
    valid: bool = False
    created_at: str = ""
    activated_at: str = ""
    retired_at: str = ""
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionRoutePromotionProfile:
    valid: bool = False
    allowed: bool = False
    route_type: str = "VENUE"
    champion_version: str = "UNAVAILABLE"
    challenger_version: str = "UNAVAILABLE"
    champion_route_name: str = "UNKNOWN"
    challenger_route_name: str = "UNKNOWN"
    champion_route_score: float = 0.0
    challenger_route_score: float = 0.0
    route_score_improvement: float = 0.0
    shortfall_improvement_bps: float = 0.0
    fill_ratio_change: float = 0.0
    latency_change_seconds: float = 0.0
    spread_change_bps: float = 0.0
    champion_governance_score: float = 0.0
    challenger_governance_score: float = 0.0
    promotion_score: float = 0.0
    promotion_grade: str = "N/A"
    promotion_severity: str = "UNKNOWN"
    recommendation: str = "HOLD_CHAMPION"
    promoted: bool = False
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionRouteRegistryProfile:
    valid: bool = False
    route_count: int = 0
    active_version: str = "UNAVAILABLE"
    champion_version: str = "UNAVAILABLE"
    challenger_versions: tuple[str, ...] = ()
    retired_versions: tuple[str, ...] = ()
    versions: tuple[ExecutionRouteVersionProfile, ...] = ()
    audit_event_count: int = 0
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
