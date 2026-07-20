from __future__ import annotations

from typing import Iterable, Mapping

from .portfolio_allocation_engine import PortfolioAllocationEngine
from .portfolio_allocation_profile import (
    AllocationCandidateProfile,
    PortfolioAllocationProfile,
)


class PortfolioAllocationService:
    def __init__(
        self,
        engine: PortfolioAllocationEngine | None = None,
    ) -> None:
        self.engine = engine or PortfolioAllocationEngine()

    def allocate(
        self,
        *,
        account_equity: float,
        candidates: Iterable[AllocationCandidateProfile],
        correlations: Mapping[tuple[str, str], float] | None = None,
    ) -> PortfolioAllocationProfile:
        return self.engine.allocate(
            account_equity=account_equity,
            candidates=candidates,
            correlations=correlations,
        )
