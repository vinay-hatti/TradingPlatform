from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class TrendOperationsPolicy:
    schema_version: str = "m52.phase6.v1"
    freshness_minutes: int = 180
    minimum_ready_ratio: float = 0.95
    minimum_health_score: float = 80.0
    minimum_governance_score: float = 90.0
    minimum_calibration_samples: int = 30
    warning_psi: float = 0.10
    critical_psi: float = 0.25
    warning_js: float = 0.10
    critical_js: float = 0.20
    permitted_nonblocking_statuses: tuple[str, ...] = ("NOT_ENOUGH_HISTORY", "DEGRADED")
