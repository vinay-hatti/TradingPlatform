from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .paper_trade_lifecycle_profile import (
    PaperPosition,
    PaperTradeLifecycleEvent,
    PaperTradeLifecycleRecord,
    PaperTradeOrder,
    PaperTradeOrderLeg,
    utc_now_iso,
)


class PaperTradeLifecycleService:
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"

    def submit(
        self,
        preparation_payload: dict[str, Any],
        *,
        registry_path: Path,
        fill_mode: str = "IMMEDIATE",
        quantity: int = 1,
    ) -> PaperTradeLifecycleRecord:
        paper_trade_ready = bool(
            preparation_payload.get("paper_trade_ready")
        )
        trade_payload = preparation_payload.get(
            "paper_trade_payload"
        )

        if not paper_trade_ready or not isinstance(
            trade_payload,
            dict,
        ):
            return self._rejected_record(
                preparation_payload,
                "PAPER_TRADE_PREPARATION_NOT_READY",
                quantity,
            )

        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        registry = self._load_registry(registry_path)
        idempotency_key = self._idempotency_key(
            trade_payload,
            quantity,
        )

        existing = registry.get(idempotency_key)
        if isinstance(existing, dict):
            record = self._record_from_dict(existing)
            return PaperTradeLifecycleRecord(
                order=record.order,
                position=record.position,
                events=record.events,
                duplicate_submission=True,
                warnings=tuple(
                    dict.fromkeys(
                        [
                            *record.warnings,
                            "DUPLICATE_SUBMISSION_RETURNED_EXISTING_ORDER",
                        ]
                    )
                ),
            )

        legs = self._build_legs(trade_payload)
        submitted_at = utc_now_iso()
        order_id = f"PAPER-{uuid4().hex[:16].upper()}"

        order = PaperTradeOrder(
            order_id=order_id,
            idempotency_key=idempotency_key,
            strategy_id=str(
                trade_payload.get("strategy_id", "")
            ),
            symbol=str(
                trade_payload.get("symbol", "")
            ).upper(),
            direction=str(
                trade_payload.get("direction", "")
            ).upper(),
            strategy_type=str(
                trade_payload.get("strategy_type", "")
            ).upper(),
            status=self.SUBMITTED,
            order_type="LIMIT_DEBIT",
            limit_debit=self._optional_number(
                trade_payload.get("limit_debit")
            ),
            quantity=quantity,
            legs=tuple(legs),
            submitted_at=submitted_at,
            metadata={
                "source": (
                    "M35_PHASE5_STEP10_PAPER_TRADE_LIFECYCLE"
                )
            },
        )

        events = [
            self._event(
                order_id,
                "ORDER_SUBMITTED",
                {
                    "status": self.SUBMITTED,
                    "limit_debit": order.limit_debit,
                    "quantity": quantity,
                },
            )
        ]
        position = None
        normalized_fill_mode = fill_mode.strip().upper()

        if normalized_fill_mode == "IMMEDIATE":
            fill_debit = order.limit_debit
            if fill_debit is None or fill_debit <= 0:
                order = PaperTradeOrder(
                    **{
                        **order.to_dict(),
                        "legs": order.legs,
                        "status": self.REJECTED,
                        "rejection_reason": (
                            "VALID_LIMIT_DEBIT_REQUIRED"
                        ),
                    }
                )
                events.append(
                    self._event(
                        order_id,
                        "ORDER_REJECTED",
                        {
                            "reason": (
                                "VALID_LIMIT_DEBIT_REQUIRED"
                            )
                        },
                    )
                )
            else:
                filled_at = utc_now_iso()
                order = PaperTradeOrder(
                    **{
                        **order.to_dict(),
                        "legs": order.legs,
                        "status": self.FILLED,
                        "filled_at": filled_at,
                        "average_fill_debit": fill_debit,
                    }
                )
                position = self._open_position(
                    order,
                    trade_payload,
                    filled_at,
                )
                events.extend(
                    [
                        self._event(
                            order_id,
                            "ORDER_FILLED",
                            {
                                "average_fill_debit": fill_debit,
                                "quantity": quantity,
                            },
                        ),
                        self._event(
                            order_id,
                            "POSITION_OPENED",
                            {
                                "position_id": (
                                    position.position_id
                                ),
                                "entry_debit": (
                                    position.entry_debit
                                ),
                            },
                        ),
                    ]
                )
        elif normalized_fill_mode != "PENDING":
            raise ValueError(
                "fill_mode must be IMMEDIATE or PENDING"
            )

        record = PaperTradeLifecycleRecord(
            order=order,
            position=position,
            events=tuple(events),
            duplicate_submission=False,
            warnings=(),
        )
        registry[idempotency_key] = record.to_dict()
        self._write_registry(registry_path, registry)
        return record

    def _rejected_record(
        self,
        preparation_payload: dict[str, Any],
        reason: str,
        quantity: int,
    ) -> PaperTradeLifecycleRecord:
        symbol = str(
            preparation_payload.get("symbol", "")
        ).upper()
        direction = str(
            preparation_payload.get("direction", "")
        ).upper()
        order_id = f"PAPER-{uuid4().hex[:16].upper()}"
        now = utc_now_iso()

        order = PaperTradeOrder(
            order_id=order_id,
            idempotency_key="",
            strategy_id=str(
                preparation_payload.get("strategy_id", "")
            ),
            symbol=symbol,
            direction=direction,
            strategy_type=str(
                preparation_payload.get("strategy_type", "")
            ),
            status=self.REJECTED,
            order_type="LIMIT_DEBIT",
            limit_debit=self._optional_number(
                preparation_payload.get("refreshed_debit")
            ),
            quantity=max(quantity, 1),
            legs=(),
            submitted_at=now,
            rejection_reason=reason,
        )
        event = self._event(
            order_id,
            "ORDER_REJECTED",
            {"reason": reason},
        )
        return PaperTradeLifecycleRecord(
            order=order,
            position=None,
            events=(event,),
            warnings=("NO_PAPER_ORDER_CREATED",),
        )

    def _build_legs(
        self,
        payload: dict[str, Any],
    ) -> list[PaperTradeOrderLeg]:
        raw_legs = payload.get("legs", [])
        if not isinstance(raw_legs, list) or not raw_legs:
            raise ValueError(
                "paper_trade_payload must contain strategy legs"
            )

        legs: list[PaperTradeOrderLeg] = []
        for raw in raw_legs:
            if not isinstance(raw, dict):
                raise ValueError("Invalid paper trade leg payload")
            action = str(raw.get("action", "")).upper()
            limit_price = (
                self._optional_number(raw.get("ask"))
                if action == "BUY"
                else self._optional_number(raw.get("bid"))
            )
            legs.append(
                PaperTradeOrderLeg(
                    symbol=str(
                        raw.get("symbol", payload.get("symbol", ""))
                    ).upper(),
                    expiry=str(raw.get("expiry", "")),
                    strike=float(raw.get("strike", 0.0)),
                    option_type=str(
                        raw.get("option_type", "")
                    ).upper(),
                    action=action,
                    quantity=int(raw.get("quantity", 1)),
                    limit_price=limit_price,
                )
            )
        return legs

    def _open_position(
        self,
        order: PaperTradeOrder,
        trade_payload: dict[str, Any],
        opened_at: str,
    ) -> PaperPosition:
        return PaperPosition(
            position_id=(
                f"POSITION-{uuid4().hex[:16].upper()}"
            ),
            order_id=order.order_id,
            strategy_id=order.strategy_id,
            symbol=order.symbol,
            direction=order.direction,
            strategy_type=order.strategy_type,
            status="OPEN",
            quantity=order.quantity,
            entry_debit=float(
                order.average_fill_debit or 0.0
            ),
            max_profit=self._optional_number(
                trade_payload.get("max_profit")
            ),
            max_loss=self._optional_number(
                trade_payload.get("max_loss")
            ),
            breakeven=self._optional_number(
                trade_payload.get("breakeven")
            ),
            reward_risk_ratio=self._optional_number(
                trade_payload.get("reward_risk_ratio")
            ),
            opened_at=opened_at,
            legs=order.legs,
        )

    def _event(
        self,
        order_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> PaperTradeLifecycleEvent:
        return PaperTradeLifecycleEvent(
            event_id=f"EVENT-{uuid4().hex[:16].upper()}",
            order_id=order_id,
            event_type=event_type,
            occurred_at=utc_now_iso(),
            payload=payload,
        )

    def _idempotency_key(
        self,
        trade_payload: dict[str, Any],
        quantity: int,
    ) -> str:
        canonical = json.dumps(
            {
                "strategy_id": trade_payload.get(
                    "strategy_id"
                ),
                "symbol": trade_payload.get("symbol"),
                "direction": trade_payload.get("direction"),
                "strategy_type": trade_payload.get(
                    "strategy_type"
                ),
                "expiry": trade_payload.get("expiry"),
                "limit_debit": trade_payload.get(
                    "limit_debit"
                ),
                "quantity": quantity,
                "legs": trade_payload.get("legs"),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        digest = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()
        return f"PAPER-{digest[:32]}"

    def _load_registry(
        self,
        path: Path,
    ) -> dict[str, Any]:
        if not path.exists():
            return {}
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
        if not isinstance(payload, dict):
            raise ValueError(
                f"Invalid paper-order registry: {path}"
            )
        return payload

    def _write_registry(
        self,
        path: Path,
        payload: dict[str, Any],
    ) -> None:
        from .paper_trade_lifecycle_serialization import (
            write_json_atomic,
        )

        write_json_atomic(path, payload)

    def _record_from_dict(
        self,
        payload: dict[str, Any],
    ) -> PaperTradeLifecycleRecord:
        order_payload = payload["order"]
        order_legs = tuple(
            PaperTradeOrderLeg(**leg)
            for leg in order_payload.get("legs", [])
        )
        order = PaperTradeOrder(
            **{
                **order_payload,
                "legs": order_legs,
            }
        )

        position_payload = payload.get("position")
        position = None
        if isinstance(position_payload, dict):
            position = PaperPosition(
                **{
                    **position_payload,
                    "legs": tuple(
                        PaperTradeOrderLeg(**leg)
                        for leg in position_payload.get(
                            "legs",
                            [],
                        )
                    ),
                }
            )

        events = tuple(
            PaperTradeLifecycleEvent(**event)
            for event in payload.get("events", [])
        )
        return PaperTradeLifecycleRecord(
            order=order,
            position=position,
            events=events,
            duplicate_submission=bool(
                payload.get("duplicate_submission")
            ),
            warnings=tuple(payload.get("warnings", [])),
        )

    def _optional_number(
        self,
        value: Any,
    ) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
