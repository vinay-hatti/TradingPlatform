from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from .profile import AutomatedPaperOrderCandidate


@dataclass(frozen=True)
class AutomatedPortfolioExposurePolicy:
    maximum_open_positions: int = 20
    maximum_capital_utilization_pct: float = 70.0
    maximum_symbol_exposure_pct: float = 20.0
    maximum_sector_exposure_pct: float = 35.0
    maximum_incremental_order_pct_of_nlv: float = 5.0
    minimum_cash_after_order_pct: float = 20.0

    def validate(self) -> None:
        for name in (
            "maximum_capital_utilization_pct",
            "maximum_symbol_exposure_pct",
            "maximum_sector_exposure_pct",
            "maximum_incremental_order_pct_of_nlv",
            "minimum_cash_after_order_pct",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be within [0, 100]")
        if self.maximum_open_positions < 1:
            raise ValueError("maximum_open_positions must be at least 1")


@dataclass(frozen=True)
class AutomatedPortfolioExposureAssessment:
    allowed: bool
    candidate_id: str
    symbol: str
    estimated_order_notional: float
    net_liquidation_value: float
    projected_capital_utilization_pct: float
    projected_cash_pct: float
    projected_symbol_exposure_pct: float
    projected_sector_exposure_pct: float
    open_position_count: int
    rejection_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutomatedPortfolioExposureEngine:
    def __init__(
        self,
        policy: AutomatedPortfolioExposurePolicy | None = None,
    ) -> None:
        self.policy = policy or AutomatedPortfolioExposurePolicy()
        self.policy.validate()

    @staticmethod
    def _bucket_pct(exposure: Mapping[str, Any], group: str, key: str) -> float:
        rows = exposure.get(group) or ()
        for row in rows:
            if str(row.get("key", "")).upper() == key.upper():
                return float(row.get("capital_pct", 0.0) or 0.0)
        return 0.0

    def assess(
        self,
        candidate: AutomatedPaperOrderCandidate,
        exposure: Mapping[str, Any],
    ) -> AutomatedPortfolioExposureAssessment:
        nlv = float(exposure.get("net_liquidation_value", 0.0) or 0.0)
        cash = float(exposure.get("cash_balance", 0.0) or 0.0)
        committed = float(exposure.get("capital_committed", 0.0) or 0.0)
        open_positions = int(exposure.get("open_position_count", 0) or 0)
        multiplier = 100.0 if candidate.asset_class.upper() == "OPTION" else 1.0
        estimated = float(candidate.quantity) * float(candidate.limit_price or 0.0) * multiplier
        sector = str(candidate.metadata.get("sector") or "UNKNOWN").upper()

        if nlv > 0:
            projected_utilization = (committed + estimated) / nlv * 100.0
            projected_cash = (cash - estimated) / nlv * 100.0
            incremental_pct = estimated / nlv * 100.0
        else:
            projected_utilization = 100.0
            projected_cash = 0.0
            incremental_pct = 100.0

        current_symbol_pct = self._bucket_pct(exposure, "by_symbol", candidate.symbol)
        current_sector_pct = self._bucket_pct(exposure, "by_sector", sector)
        projected_symbol_pct = current_symbol_pct + incremental_pct
        projected_sector_pct = current_sector_pct + incremental_pct

        reasons: list[str] = []
        warnings: list[str] = []
        if nlv <= 0:
            reasons.append("NET_LIQUIDATION_VALUE_NOT_AVAILABLE")
        if open_positions >= self.policy.maximum_open_positions:
            reasons.append("MAXIMUM_OPEN_POSITIONS_REACHED")
        if projected_utilization > self.policy.maximum_capital_utilization_pct:
            reasons.append("PROJECTED_CAPITAL_UTILIZATION_EXCEEDED")
        if projected_cash < self.policy.minimum_cash_after_order_pct:
            reasons.append("PROJECTED_CASH_RESERVE_BELOW_MINIMUM")
        if incremental_pct > self.policy.maximum_incremental_order_pct_of_nlv:
            reasons.append("INCREMENTAL_ORDER_SIZE_EXCEEDED")
        if projected_symbol_pct > self.policy.maximum_symbol_exposure_pct:
            reasons.append("PROJECTED_SYMBOL_EXPOSURE_EXCEEDED")
        if projected_sector_pct > self.policy.maximum_sector_exposure_pct:
            reasons.append("PROJECTED_SECTOR_EXPOSURE_EXCEEDED")
        if sector == "UNKNOWN":
            warnings.append("SECTOR_NOT_AVAILABLE")

        return AutomatedPortfolioExposureAssessment(
            allowed=not reasons,
            candidate_id=candidate.candidate_id,
            symbol=candidate.symbol,
            estimated_order_notional=round(estimated, 6),
            net_liquidation_value=round(nlv, 2),
            projected_capital_utilization_pct=round(projected_utilization, 4),
            projected_cash_pct=round(projected_cash, 4),
            projected_symbol_exposure_pct=round(projected_symbol_pct, 4),
            projected_sector_exposure_pct=round(projected_sector_pct, 4),
            open_position_count=open_positions,
            rejection_reasons=tuple(dict.fromkeys(reasons)),
            warnings=tuple(dict.fromkeys(warnings)),
            metadata={
                "sector": sector,
                "paper_only": True,
                "live_trading_enabled": False,
            },
        )
