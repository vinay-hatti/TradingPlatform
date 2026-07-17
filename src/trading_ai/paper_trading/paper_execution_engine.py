from __future__ import annotations

from datetime import datetime, timezone

from .paper_execution_policy import PaperExecutionPolicy
from .paper_execution_profile import (
    PaperExecutionCheck,
    PaperExecutionDecision,
    PaperExecutionRecord,
    PaperExecutionRequest,
)
from .paper_fill_simulator import PaperFillSimulator


class PaperExecutionEngine:
    def __init__(
        self,
        policy: PaperExecutionPolicy | None = None,
    ) -> None:
        self.policy = policy or PaperExecutionPolicy()
        self.policy.validate()
        self.simulator = PaperFillSimulator(self.policy)

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate(
        self,
        request: PaperExecutionRequest,
    ) -> PaperExecutionDecision:
        command = request.order_draft.command
        checks = []

        def add(name, passed, message, metadata=None):
            checks.append(
                PaperExecutionCheck(
                    name=name,
                    passed=bool(passed),
                    required=True,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                    metadata=metadata or {},
                )
            )

        add("execution_key", bool(request.execution_key), "Execution key is required.")
        add(
            "order_type",
            command.order_type.upper() in self.policy.allowed_order_types,
            "Order type is supported.",
        )
        add(
            "time_in_force",
            command.time_in_force.upper() in self.policy.allowed_time_in_force,
            "Time in force is supported.",
        )
        add("legs", bool(command.legs), "At least one order leg is required.")
        for leg in command.legs:
            add(
                f"quote:{leg.leg_id}",
                leg.symbol in request.quotes,
                "A market quote is available for each leg.",
            )
            add(
                f"quantity:{leg.leg_id}",
                leg.quantity > 0,
                "Leg quantity is positive.",
            )

        failed = [check for check in checks if not check.passed]
        score = (
            sum(check.score for check in checks) / len(checks)
            if checks else 100.0
        )
        if failed:
            grade, severity = self._grade(score)
            return PaperExecutionDecision(
                valid=True,
                allowed=False,
                execution_key=request.execution_key,
                aggregate_id=command.aggregate_id,
                score=round(score, 2),
                grade=grade,
                severity=severity,
                recommendation="REJECT",
                checks=tuple(checks),
                rejection_reasons=tuple(
                    check.name.upper() for check in failed
                ),
            )

        fills = self.simulator.simulate(request)
        requested_quantity = max(
            abs(float(leg.quantity)) for leg in command.legs
        )
        filled_quantity = max(
            (fill.quantity for fill in fills),
            default=0.0,
        )
        remaining = max(0.0, requested_quantity - filled_quantity)
        if filled_quantity <= 0:
            status = "WORKING"
        elif remaining > 0:
            status = "PARTIALLY_FILLED"
        else:
            status = "FILLED"

        gross_value = sum(
            fill.quantity * fill.fill_price for fill in fills
        )
        commissions = sum(fill.commission for fill in fills)
        signed_cash = 0.0
        for fill in fills:
            direction = (
                1.0 if fill.side.upper().startswith("SELL") else -1.0
            )
            signed_cash += (
                direction * fill.quantity * fill.fill_price
            )
        average_fill_price = (
            sum(fill.quantity * fill.fill_price for fill in fills)
            / sum(fill.quantity for fill in fills)
            if fills
            else None
        )
        latency_ms = max(
            (fill.latency_ms for fill in fills),
            default=self.policy.default_latency_ms,
        )
        now = datetime.now(timezone.utc).isoformat()
        record = PaperExecutionRecord(
            execution_key=request.execution_key,
            session_id=request.session_id,
            cycle_id=request.cycle_id,
            aggregate_id=command.aggregate_id,
            client_order_id=command.client_order_id,
            account_id=command.account_id,
            order_type=command.order_type,
            time_in_force=command.time_in_force,
            status=status,
            requested_quantity=requested_quantity,
            filled_quantity=round(filled_quantity, 6),
            remaining_quantity=round(remaining, 6),
            average_fill_price=(
                round(average_fill_price, 6)
                if average_fill_price is not None
                else None
            ),
            gross_value=round(gross_value, 6),
            commissions=round(commissions, 6),
            net_cash_flow=round(signed_cash - commissions, 6),
            latency_ms=latency_ms,
            fills=fills,
            created_at=now,
            updated_at=now,
        )
        grade, severity = self._grade(score)
        return PaperExecutionDecision(
            valid=True,
            allowed=True,
            execution_key=request.execution_key,
            aggregate_id=command.aggregate_id,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation=(
                "MONITOR" if status == "WORKING" else "RECORD_FILL"
            ),
            record=record,
            checks=tuple(checks),
        )
