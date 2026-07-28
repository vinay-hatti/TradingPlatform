from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping

from .exposure_engine import (
    AutomatedPortfolioExposureAssessment,
    AutomatedPortfolioExposureEngine,
)
from .institutional_adapter import InstitutionalDecisionHandoffAdapter
from .service import AutomatedPaperOrderHandoffService


@dataclass(frozen=True)
class AutomatedPaperTradingPhaseResult:
    milestone: int
    phase: int
    mode: str
    total_decisions: int
    conversion_accepted: int
    conversion_rejected: int
    exposure_accepted: int
    exposure_rejected: int
    handoff_succeeded: int
    handoff_rejected: int
    results: tuple[dict[str, Any], ...] = ()
    status: str = "UNKNOWN"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutomatedPaperTradingPhaseService:
    """Complete Milestone 51 Phase 1 institutional-to-broker orchestration."""

    def __init__(
        self,
        session_factory: Callable,
        *,
        exposure_provider: Callable[[str], Mapping[str, Any]],
        broker_order_service=None,
        adapter: InstitutionalDecisionHandoffAdapter | None = None,
        exposure_engine: AutomatedPortfolioExposureEngine | None = None,
    ) -> None:
        self.adapter = adapter or InstitutionalDecisionHandoffAdapter()
        self.exposure_engine = exposure_engine or AutomatedPortfolioExposureEngine()
        self.exposure_provider = exposure_provider
        self.handoff = AutomatedPaperOrderHandoffService(
            session_factory,
            broker_order_service=broker_order_service,
        )

    def execute(
        self,
        payload: Mapping[str, Any],
        *,
        mode: str = "DRY_RUN",
        confirmation: str = "",
        maximum_orders: int = 10,
    ) -> AutomatedPaperTradingPhaseResult:
        if maximum_orders < 1:
            raise ValueError("maximum_orders must be at least 1")

        conversions = self.adapter.convert_payload(payload)
        accepted = [row for row in conversions if row.accepted and row.candidate is not None]
        exposure = self.exposure_provider("PAPER-PRIMARY")

        rows: list[dict[str, Any]] = []
        exposure_accepted = 0
        exposure_rejected = 0
        handoff_succeeded = 0
        handoff_rejected = 0

        for conversion in accepted[:maximum_orders]:
            candidate = conversion.candidate
            assert candidate is not None
            exposure_assessment = self.exposure_engine.assess(candidate, exposure)
            row: dict[str, Any] = {
                "symbol": candidate.symbol,
                "candidate_id": candidate.candidate_id,
                "conversion": {
                    "accepted": True,
                    "warnings": list(conversion.warnings),
                    "metadata": conversion.metadata,
                },
                "exposure_assessment": exposure_assessment.to_dict(),
                "handoff": None,
            }
            if not exposure_assessment.allowed:
                exposure_rejected += 1
                rows.append(row)
                continue

            exposure_accepted += 1
            handoff_result = self.handoff.execute(
                candidate,
                mode=mode,
                confirmation=confirmation,
            )
            row["handoff"] = handoff_result.to_dict()
            if handoff_result.status == "REJECTED_BY_HANDOFF_POLICY":
                handoff_rejected += 1
            else:
                handoff_succeeded += 1
            rows.append(row)

        for conversion in conversions:
            if conversion.accepted:
                continue
            rows.append({
                "symbol": conversion.symbol,
                "candidate_id": None,
                "conversion": {
                    "accepted": False,
                    "rejection_reasons": list(conversion.rejection_reasons),
                    "warnings": list(conversion.warnings),
                    "metadata": conversion.metadata,
                },
                "exposure_assessment": None,
                "handoff": None,
            })

        if not accepted:
            status = "NO_APPROVED_INSTITUTIONAL_DECISIONS"
        elif handoff_succeeded:
            status = "PHASE1_AUTOMATED_PAPER_HANDOFF_COMPLETED"
        elif exposure_rejected:
            status = "PHASE1_BLOCKED_BY_PORTFOLIO_EXPOSURE"
        else:
            status = "PHASE1_NO_ORDERS_CREATED"

        return AutomatedPaperTradingPhaseResult(
            milestone=51,
            phase=1,
            mode=mode.upper(),
            total_decisions=len(conversions),
            conversion_accepted=len(accepted),
            conversion_rejected=len(conversions) - len(accepted),
            exposure_accepted=exposure_accepted,
            exposure_rejected=exposure_rejected,
            handoff_succeeded=handoff_succeeded,
            handoff_rejected=handoff_rejected,
            results=tuple(rows),
            status=status,
            metadata={
                "maximum_orders": maximum_orders,
                "orders_truncated": max(0, len(accepted) - maximum_orders),
                "environment": "PAPER",
                "live_trading_enabled": False,
                "workflow": [
                    "INSTITUTIONAL_DECISION",
                    "CANDIDATE_CONVERSION",
                    "PORTFOLIO_EXPOSURE_GATE",
                    "CANONICAL_ORDER",
                    "IBKR_PAPER_HANDOFF",
                ],
            },
        )
