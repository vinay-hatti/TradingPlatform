from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from .policy import AutomatedOrderLifecyclePolicy
from .profile import (
    BrokerExecutionSnapshot,
    BrokerOrderLifecycleSnapshot,
    LifecycleAction,
    PaperPositionProjection,
)


def _parse(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:24]
    return f"{prefix}-{digest.upper()}"


class AutomatedOrderLifecycleEngine:
    def __init__(
        self,
        policy: AutomatedOrderLifecyclePolicy | None = None,
    ) -> None:
        self.policy = policy or AutomatedOrderLifecyclePolicy()
        self.policy.validate()

    @staticmethod
    def normalize_status(status: str) -> str:
        value = str(status or "").upper().replace(" ", "").replace("_", "")
        mapping = {
            "CANCELLED": "CANCELED",
            "APICANCELLED": "CANCELED",
            "PENDINGCANCEL": "PENDING_CANCEL",
            "CANCELREQUESTED": "CANCEL_REQUESTED",
            "PARTIALLYFILLED": "PARTIALLY_FILLED",
            "PRESUBMITTED": "PRE_SUBMITTED",
            "PENDINGSUBMIT": "PENDING_SUBMIT",
        }
        return mapping.get(value, value)

    def classify(
        self,
        order: BrokerOrderLifecycleSnapshot,
        *,
        now: datetime | None = None,
    ) -> LifecycleAction:
        current = now or datetime.now(timezone.utc)
        status = self.normalize_status(order.status)
        age_minutes = max(
            0.0,
            (current - _parse(order.updated_at or order.submitted_at)).total_seconds()
            / 60.0,
        )
        terminal = status in {"FILLED", "CANCELED", "REJECTED", "INACTIVE"}
        partial = order.filled_quantity > 0 and order.remaining_quantity > 0

        if terminal:
            return LifecycleAction(
                aggregate_id=order.aggregate_id,
                broker_order_id=order.broker_order_id,
                action="NO_ACTION",
                reason="ORDER_TERMINAL",
                allowed=True,
                metadata={"normalized_status": status, "age_minutes": age_minutes},
            )

        threshold = (
            self.policy.stale_partial_fill_minutes
            if partial
            else self.policy.stale_submitted_minutes
        )
        if age_minutes >= threshold:
            return LifecycleAction(
                aggregate_id=order.aggregate_id,
                broker_order_id=order.broker_order_id,
                action="CANCEL_STALE_ORDER",
                reason=(
                    "STALE_PARTIAL_FILL"
                    if partial
                    else "STALE_WORKING_ORDER"
                ),
                allowed=self.policy.automatic_cancellation_enabled,
                confirmation_required=True,
                metadata={
                    "normalized_status": status,
                    "age_minutes": round(age_minutes, 4),
                    "threshold_minutes": threshold,
                    "filled_quantity": order.filled_quantity,
                    "remaining_quantity": order.remaining_quantity,
                },
            )

        return LifecycleAction(
            aggregate_id=order.aggregate_id,
            broker_order_id=order.broker_order_id,
            action="MONITOR",
            reason="ORDER_ACTIVE_WITHIN_THRESHOLD",
            allowed=True,
            metadata={
                "normalized_status": status,
                "age_minutes": round(age_minutes, 4),
                "threshold_minutes": threshold,
            },
        )

    def actions(
        self,
        orders: Iterable[BrokerOrderLifecycleSnapshot],
        *,
        now: datetime | None = None,
    ) -> tuple[LifecycleAction, ...]:
        return tuple(self.classify(order, now=now) for order in orders)

    def project_positions(
        self,
        portfolio_id: str,
        executions: Iterable[BrokerExecutionSnapshot],
    ) -> tuple[PaperPositionProjection, ...]:
        grouped: dict[str, list[BrokerExecutionSnapshot]] = defaultdict(list)
        for execution in executions:
            grouped[execution.aggregate_id].append(execution)

        projections: list[PaperPositionProjection] = []
        for aggregate_id, rows in grouped.items():
            ordered = sorted(rows, key=lambda row: (_parse(row.executed_at), row.execution_id))
            signed_quantity = 0.0
            signed_notional = 0.0
            total_commission = 0.0
            for row in ordered:
                sign = 1.0 if row.side.upper() in {"BUY", "BOT"} else -1.0
                signed_quantity += sign * float(row.quantity)
                signed_notional += sign * float(row.quantity) * float(row.price)
                total_commission += float(row.commission or 0.0)

            if abs(signed_quantity) < 1e-12:
                status = "CLOSED"
                direction = "FLAT"
                quantity = 0.0
                average_price = 0.0
            else:
                status = "OPEN"
                direction = "LONG" if signed_quantity > 0 else "SHORT"
                quantity = abs(signed_quantity)
                average_price = abs(signed_notional / signed_quantity)

            first = ordered[0]
            last = ordered[-1]
            projections.append(
                PaperPositionProjection(
                    position_id=_stable_id(
                        "M51-POS",
                        portfolio_id,
                        aggregate_id,
                        first.symbol,
                        first.security_type,
                    ),
                    portfolio_id=portfolio_id,
                    aggregate_id=aggregate_id,
                    symbol=first.symbol,
                    security_type=first.security_type,
                    direction=direction,
                    quantity=round(quantity, 8),
                    average_entry_price=round(average_price, 8),
                    total_commission=round(total_commission, 8),
                    currency=first.currency,
                    opened_at=first.executed_at,
                    last_execution_at=last.executed_at,
                    execution_ids=tuple(row.execution_id for row in ordered),
                    status=status,
                    metadata={
                        "execution_count": len(ordered),
                        "broker_order_ids": sorted(
                            {row.broker_order_id for row in ordered}
                        ),
                        "paper_only": True,
                        "live_trading_enabled": False,
                    },
                )
            )
        return tuple(sorted(projections, key=lambda row: row.position_id))
