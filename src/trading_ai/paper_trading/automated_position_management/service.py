from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Mapping

from trading_ai.paper_trading.automated_order_handoff import (
    AutomatedPaperOrderCandidate,
    AutomatedPaperOrderHandoffService,
)

from .adapter import LifecyclePositionAdapter
from .engine import AutomatedPositionManagementEngine
from .policy import AutomatedPositionManagementPolicy
from .profile import AutomatedPositionManagementResult


class AutomatedPositionManagementService:
    def __init__(
        self,
        session_factory: Callable,
        *,
        policy: AutomatedPositionManagementPolicy | None = None,
        broker_order_service=None,
    ) -> None:
        self.policy = policy or AutomatedPositionManagementPolicy()
        self.policy.validate()
        self.adapter = LifecyclePositionAdapter()
        self.engine = AutomatedPositionManagementEngine(self.policy)
        self.handoff = AutomatedPaperOrderHandoffService(
            session_factory,
            broker_order_service=broker_order_service,
        )

    def execute(
        self,
        lifecycle_report: Mapping[str, Any],
        market_prices: Mapping[str, Any],
        *,
        mode: str = "DRY_RUN",
        confirmation: str = "",
    ) -> AutomatedPositionManagementResult:
        normalized_mode = mode.upper()
        if normalized_mode not in {"DRY_RUN", "SUBMIT"}:
            raise ValueError("mode must be DRY_RUN or SUBMIT")

        portfolio_id = str(
            lifecycle_report.get("portfolio_id") or "PAPER-PRIMARY"
        )
        positions = self.adapter.from_report(lifecycle_report, market_prices)
        assessments, intents = self.engine.evaluate(positions)

        submissions: list[dict[str, Any]] = []
        if normalized_mode == "SUBMIT":
            expected = self.policy.submission_confirmation_template.format(
                portfolio_id=portfolio_id
            )
            if confirmation != expected:
                raise PermissionError(
                    "submission confirmation mismatch; expected exactly: "
                    + expected
                )

            for intent in intents[: self.policy.maximum_exit_orders_per_run]:
                candidate = AutomatedPaperOrderCandidate(
                    candidate_id=intent.intent_id,
                    portfolio_id=intent.portfolio_id,
                    symbol=intent.symbol,
                    asset_class=intent.asset_class,
                    side=intent.side,
                    quantity=intent.quantity,
                    order_type=intent.order_type,
                    time_in_force=intent.time_in_force,
                    limit_price=intent.limit_price,
                    expiry=intent.expiry,
                    strike=intent.strike,
                    right=intent.right,
                    local_symbol=intent.local_symbol,
                    contract_id=intent.contract_id,
                    currency=intent.currency,
                    institutional_allowed=True,
                    risk_gateway_allowed=True,
                    decision_score=100.0,
                    probability=1.0,
                    strategy_name="AUTOMATED_POSITION_EXIT",
                    metadata={
                        **intent.metadata,
                        "position_effect": "CLOSE",
                        "exit_reason": intent.reason,
                    },
                )
                result = self.handoff.execute(
                    candidate,
                    mode="SUBMIT",
                    confirmation=(
                        f"SUBMIT AUTOMATED IBKR PAPER ORDER {portfolio_id}"
                    ),
                )
                submissions.append(result.to_dict())

        blocked = sum(not assessment.allowed for assessment in assessments)
        exits = sum(
            assessment.action == "EXIT" and assessment.allowed
            for assessment in assessments
        )
        monitor = sum(
            assessment.action == "MONITOR" and assessment.allowed
            for assessment in assessments
        )
        if not positions:
            status = "NO_OPEN_POSITIONS"
        elif submissions:
            status = "PHASE3_EXIT_ORDERS_SUBMITTED"
        elif exits:
            status = "PHASE3_EXIT_ACTIONS_READY"
        else:
            status = "PHASE3_POSITIONS_MONITORED"

        warnings: list[str] = []
        if exits and normalized_mode == "DRY_RUN":
            warnings.append("EXIT_ACTIONS_REQUIRE_OPERATOR_REVIEW")
        if len(intents) > self.policy.maximum_exit_orders_per_run:
            warnings.append("EXIT_ORDER_LIMIT_APPLIED")

        return AutomatedPositionManagementResult(
            milestone=51,
            phase=3,
            portfolio_id=portfolio_id,
            mode=normalized_mode,
            total_positions=len(positions),
            exit_candidates=exits,
            monitor_only=monitor,
            blocked_exits=blocked,
            submitted_exits=len(submissions),
            assessments=tuple(asdict(row) for row in assessments),
            intents=tuple(asdict(row) for row in intents),
            submissions=tuple(submissions),
            status=status,
            warnings=tuple(warnings),
            metadata={
                "environment": "PAPER",
                "live_trading_enabled": False,
                "maximum_exit_orders_per_run": (
                    self.policy.maximum_exit_orders_per_run
                ),
            },
        )
