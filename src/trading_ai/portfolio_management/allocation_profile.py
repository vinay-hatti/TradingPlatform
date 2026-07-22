from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

@dataclass(frozen=True)
class CapitalAllocationProfile:
    reserve_cash_pct: float = 0.20
    minimum_reserve_dollars: float = 5000.0
    maximum_deployment_pct: float = 0.50
    maximum_incremental_risk_pct: float = 0.10
    score_weight: float = 0.45
    return_weight: float = 0.20
    fit_weight: float = 0.20
    diversification_weight: float = 0.15
    minimum_allocation_dollars: float = 100.0
    maximum_allocation_per_candidate_pct: float = 0.10
    def to_dict(self) -> dict[str, Any]: return asdict(self)
