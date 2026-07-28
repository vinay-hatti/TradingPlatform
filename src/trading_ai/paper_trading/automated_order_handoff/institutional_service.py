from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping

from .institutional_adapter import (
    InstitutionalDecisionHandoffAdapter,
    InstitutionalDecisionHandoffConversion,
)
from .profile import AutomatedPaperOrderHandoffResult
from .service import AutomatedPaperOrderHandoffService


@dataclass(frozen=True)
class InstitutionalDecisionBatchHandoffResult:
    milestone: int
    phase: int
    step: int
    mode: str
    total_decisions: int
    accepted_conversions: int
    rejected_conversions: int
    handoff_succeeded: int
    handoff_rejected: int
    conversion_results: tuple[dict[str, Any], ...] = ()
    handoff_results: tuple[dict[str, Any], ...] = ()
    status: str = "UNKNOWN"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InstitutionalDecisionBatchHandoffService:
    def __init__(
        self,
        session_factory: Callable,
        *,
        adapter: InstitutionalDecisionHandoffAdapter | None = None,
        broker_order_service=None,
    ) -> None:
        self.adapter = adapter or InstitutionalDecisionHandoffAdapter()
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
    ) -> InstitutionalDecisionBatchHandoffResult:
        if maximum_orders < 1:
            raise ValueError("maximum_orders must be at least 1")

        conversions = self.adapter.convert_payload(payload)
        accepted = [item for item in conversions if item.accepted]
        selected = accepted[:maximum_orders]

        results: list[AutomatedPaperOrderHandoffResult] = []
        for conversion in selected:
            assert conversion.candidate is not None
            results.append(
                self.handoff.execute(
                    conversion.candidate,
                    mode=mode,
                    confirmation=confirmation,
                )
            )

        conversion_payload = tuple(
            {
                "symbol": item.symbol,
                "accepted": item.accepted,
                "candidate": (
                    None
                    if item.candidate is None
                    else asdict(item.candidate)
                ),
                "rejection_reasons": list(item.rejection_reasons),
                "warnings": list(item.warnings),
                "metadata": item.metadata,
            }
            for item in conversions
        )
        handoff_payload = tuple(item.to_dict() for item in results)
        handoff_rejected = sum(
            item.status == "REJECTED_BY_HANDOFF_POLICY" for item in results
        )
        status = (
            "NO_APPROVED_INSTITUTIONAL_DECISIONS"
            if not accepted
            else "INSTITUTIONAL_HANDOFF_BATCH_COMPLETED"
        )
        return InstitutionalDecisionBatchHandoffResult(
            milestone=51,
            phase=1,
            step=2,
            mode=mode.upper(),
            total_decisions=len(conversions),
            accepted_conversions=len(accepted),
            rejected_conversions=len(conversions) - len(accepted),
            handoff_succeeded=len(results) - handoff_rejected,
            handoff_rejected=handoff_rejected,
            conversion_results=conversion_payload,
            handoff_results=handoff_payload,
            status=status,
            metadata={
                "maximum_orders": maximum_orders,
                "orders_truncated": max(0, len(accepted) - len(selected)),
                "environment": "PAPER",
                "live_trading_enabled": False,
            },
        )
