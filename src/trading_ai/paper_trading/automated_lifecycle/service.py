from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Callable

from trading_ai.broker.ibkr.order_service import (
    IbkrPaperOrderGovernanceService,
    IbkrPaperOrderService,
)

from .engine import AutomatedOrderLifecycleEngine
from .policy import AutomatedOrderLifecyclePolicy
from .profile import AutomatedLifecycleResult
from .repository import AutomatedLifecycleRepository


class AutomatedPaperOrderLifecycleService:
    def __init__(
        self,
        session_factory: Callable,
        transport,
        *,
        policy: AutomatedOrderLifecyclePolicy | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.transport = transport
        self.policy = policy or AutomatedOrderLifecyclePolicy()
        self.policy.validate()
        self.engine = AutomatedOrderLifecycleEngine(self.policy)
        self.repository = AutomatedLifecycleRepository(session_factory)
        self.governance = IbkrPaperOrderGovernanceService(session_factory)
        self.broker = IbkrPaperOrderService(session_factory, transport)

    def execute(
        self,
        portfolio_id: str = "PAPER-PRIMARY",
        *,
        mode: str = "MONITOR",
        confirmation: str = "",
        now: datetime | None = None,
    ) -> AutomatedLifecycleResult:
        normalized_mode = mode.upper()
        if normalized_mode not in {"MONITOR", "CANCEL_STALE"}:
            raise ValueError("mode must be MONITOR or CANCEL_STALE")

        control = self.governance.status(portfolio_id)
        if control["environment"] != "PAPER" or control["live_trading_enabled"]:
            raise PermissionError("paper-only lifecycle governance failed")

        synchronization = self.broker.synchronize(portfolio_id)
        orders = self.repository.orders(portfolio_id)
        executions = self.repository.executions(portfolio_id)
        actions = self.engine.actions(
            orders,
            now=now or datetime.now(timezone.utc),
        )
        positions = self.engine.project_positions(portfolio_id, executions)

        cancellations: list[dict] = []
        candidates = [
            action
            for action in actions
            if action.action == "CANCEL_STALE_ORDER"
        ]
        if normalized_mode == "CANCEL_STALE":
            expected = self.policy.cancellation_confirmation_template.format(
                portfolio_id=portfolio_id
            )
            if confirmation != expected:
                raise PermissionError(
                    "cancellation confirmation mismatch; expected exactly: "
                    + expected
                )
            if not control["paper_order_submission_enabled"]:
                raise PermissionError("paper-order routing must be enabled")
            for action in candidates[: self.policy.maximum_cancel_actions_per_run]:
                cancellations.append(
                    self.broker.cancel(portfolio_id, action.aggregate_id)
                )

        summary = {
            "order_count": len(orders),
            "execution_count": len(executions),
            "position_count": len(positions),
            "open_positions": sum(p.status == "OPEN" for p in positions),
            "closed_positions": sum(p.status == "CLOSED" for p in positions),
            "terminal_orders": sum(
                self.engine.normalize_status(o.status)
                in {"FILLED", "CANCELED", "REJECTED", "INACTIVE"}
                for o in orders
            ),
            "active_orders": sum(
                self.engine.normalize_status(o.status)
                not in {"FILLED", "CANCELED", "REJECTED", "INACTIVE"}
                for o in orders
            ),
            "stale_orders": len(candidates),
            "cancellations_requested": len(cancellations),
        }
        status = (
            "PHASE2_STALE_CANCELLATIONS_REQUESTED"
            if cancellations
            else "PHASE2_LIFECYCLE_SYNCHRONIZED"
        )
        warnings: list[str] = []
        if candidates and normalized_mode == "MONITOR":
            warnings.append("STALE_ORDERS_REQUIRE_OPERATOR_REVIEW")
        if not executions:
            warnings.append("NO_BROKER_EXECUTIONS_AVAILABLE")

        return AutomatedLifecycleResult(
            milestone=51,
            phase=2,
            portfolio_id=portfolio_id,
            mode=normalized_mode,
            synchronization=synchronization,
            orders=tuple(asdict(row) for row in orders),
            actions=tuple(asdict(row) for row in actions),
            cancellations=tuple(cancellations),
            positions=tuple(asdict(row) for row in positions),
            summary=summary,
            status=status,
            warnings=tuple(warnings),
            metadata={
                "environment": "PAPER",
                "live_trading_enabled": False,
                "automatic_cancellation_enabled": (
                    self.policy.automatic_cancellation_enabled
                ),
                "control": control,
            },
        )
