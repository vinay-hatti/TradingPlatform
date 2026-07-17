from __future__ import annotations

from typing import Any

from .broker_execution_policy import BrokerExecutionPolicy
from .broker_execution_profile import (
    BrokerExecutionCheckProfile,
    BrokerOrderExecutionResult,
    BrokerOrderStateProfile,
)
from .broker_order_profile import BrokerOrderValidationProfile
from .broker_profile import BrokerReadinessProfile


class BrokerExecutionEngine:
    """Govern submission, cancel, and replacement readiness."""

    def __init__(
        self,
        policy: BrokerExecutionPolicy | None = None,
    ) -> None:
        self.policy = policy or BrokerExecutionPolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95.0:
            return "A", "LOW"
        if score >= 85.0:
            return "B", "MODERATE"
        if score >= 70.0:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate(
        self,
        *,
        action: str,
        broker: str,
        client_order_id: str,
        idempotency_key: str | None,
        readiness: BrokerReadinessProfile | None = None,
        validation: BrokerOrderValidationProfile | None = None,
        order_state: BrokerOrderStateProfile | None = None,
        replayed: bool = False,
        extra_checks: tuple[tuple[str, bool, str], ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> BrokerOrderExecutionResult:
        checks: list[BrokerExecutionCheckProfile] = []

        def add(
            name: str,
            passed: bool,
            message: str,
            *,
            required: bool = True,
            check_metadata: dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                BrokerExecutionCheckProfile(
                    name=name,
                    passed=bool(passed),
                    required=required,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                    metadata=check_metadata or {},
                )
            )

        add(
            "broker_readiness",
            readiness is not None and readiness.allowed,
            "Broker readiness must be approved.",
            required=self.policy.require_broker_readiness,
        )

        if action.upper() in {"SUBMIT", "REPLACE"} and not replayed:
            add(
                "order_validation",
                validation is not None and validation.allowed,
                "Order validation must be approved.",
                required=self.policy.require_order_validation,
            )

        add(
            "idempotency_key",
            bool(idempotency_key)
            or not self.policy.require_idempotency_key,
            "Idempotency key is required.",
            required=self.policy.require_idempotency_key,
        )

        for name, passed, message in extra_checks:
            add(name, passed, message)

        required = [check for check in checks if check.required]
        failed = [check for check in required if not check.passed]
        score = (
            sum(check.score for check in required) / len(required)
            if required else 100.0
        )

        allowed = (
            not failed
            and score >= self.policy.minimum_execution_score
        )
        if not self.policy.fail_closed:
            allowed = score >= self.policy.minimum_execution_score

        grade, severity = self._grade(score)

        status = (
            order_state.status
            if order_state is not None
            else "REJECTED"
            if not allowed
            else "APPROVED"
        )

        return BrokerOrderExecutionResult(
            valid=True,
            allowed=allowed,
            action=action.upper(),
            status=status,
            broker=broker,
            client_order_id=client_order_id,
            broker_order_id=(
                order_state.broker_order_id
                if order_state is not None
                else None
            ),
            idempotency_key=idempotency_key,
            replayed=replayed,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation=(
                "RETURN_CACHED_RESULT"
                if replayed and allowed
                else "ACCEPT"
                if allowed
                else "REJECT"
            ),
            order_state=order_state,
            validation=validation,
            readiness=readiness,
            checks=tuple(checks),
            rejection_reasons=tuple(
                check.name.upper() for check in failed
            ),
            metadata=metadata or {},
        )
