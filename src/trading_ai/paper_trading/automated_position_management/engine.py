from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Iterable

from .policy import AutomatedPositionManagementPolicy
from .profile import (
    ManagedPaperPosition,
    PositionExitAssessment,
    PositionExitOrderIntent,
)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_date(value: str) -> date:
    text = str(value).replace("-", "")
    return datetime.strptime(text, "%Y%m%d").date()


def _stable(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:24]
    return f"{prefix}-{digest.upper()}"


class AutomatedPositionManagementEngine:
    def __init__(
        self,
        policy: AutomatedPositionManagementPolicy | None = None,
    ) -> None:
        self.policy = policy or AutomatedPositionManagementPolicy()
        self.policy.validate()

    def assess(
        self,
        position: ManagedPaperPosition,
        *,
        now: datetime | None = None,
    ) -> PositionExitAssessment:
        current = now or datetime.now(timezone.utc)
        reasons: list[str] = []
        warnings: list[str] = []

        entry = float(position.average_entry_price)
        market = float(position.current_price)
        quantity = float(position.quantity)
        if entry <= 0:
            reasons.append("ENTRY_PRICE_NOT_AVAILABLE")
        if quantity <= 0:
            reasons.append("POSITION_QUANTITY_NOT_AVAILABLE")
        if self.policy.require_positive_market_price and market <= 0:
            reasons.append("MARKET_PRICE_NOT_AVAILABLE")

        direction = position.direction.upper()
        if direction not in {"LONG", "SHORT"}:
            reasons.append("POSITION_DIRECTION_NOT_SUPPORTED")

        if entry > 0:
            signed_move = (
                (market - entry) / entry
                if direction == "LONG"
                else (entry - market) / entry
            )
        else:
            signed_move = 0.0
        return_pct = signed_move * 100.0
        multiplier = 100.0 if position.security_type.upper() in {"OPT", "OPTION"} else 1.0
        unrealized = signed_move * entry * quantity * multiplier
        holding_minutes = max(
            0.0,
            (current - _parse_datetime(position.opened_at)).total_seconds() / 60.0,
        )

        trigger = "NONE"
        urgency = "LOW"
        action = "MONITOR"
        if not reasons:
            if return_pct >= self.policy.take_profit_pct:
                trigger = "TAKE_PROFIT"
                urgency = "HIGH"
                action = "EXIT"
            elif return_pct <= self.policy.stop_loss_pct:
                trigger = "STOP_LOSS"
                urgency = "CRITICAL"
                action = "EXIT"
            elif holding_minutes >= self.policy.maximum_holding_minutes:
                trigger = "MAX_HOLDING_TIME"
                urgency = "MODERATE"
                action = "EXIT"
            elif position.security_type.upper() in {"OPT", "OPTION"} and position.expiry:
                dte = (_parse_date(position.expiry) - current.date()).days
                if dte <= self.policy.option_exit_dte:
                    trigger = "OPTION_EXPIRY_WINDOW"
                    urgency = "HIGH"
                    action = "EXIT"
                if dte < 0:
                    warnings.append("OPTION_ALREADY_EXPIRED")
            elif position.security_type.upper() in {"OPT", "OPTION"}:
                warnings.append("OPTION_EXPIRY_NOT_AVAILABLE")

        if direction == "LONG":
            target_price = entry * (1.0 + self.policy.take_profit_pct / 100.0)
            stop_price = entry * (1.0 + self.policy.stop_loss_pct / 100.0)
        else:
            target_price = entry * (1.0 - self.policy.take_profit_pct / 100.0)
            stop_price = entry * (1.0 - self.policy.stop_loss_pct / 100.0)

        return PositionExitAssessment(
            position_id=position.position_id,
            symbol=position.symbol,
            action=action,
            trigger=trigger,
            allowed=not reasons,
            urgency=urgency,
            unrealized_pnl=round(unrealized, 8),
            unrealized_return_pct=round(return_pct, 6),
            holding_minutes=round(holding_minutes, 4),
            target_price=round(target_price, 8),
            stop_price=round(stop_price, 8),
            exit_quantity=quantity,
            rejection_reasons=tuple(dict.fromkeys(reasons)),
            warnings=tuple(dict.fromkeys(warnings)),
            metadata={
                "security_type": position.security_type,
                "direction": direction,
                "paper_only": True,
                "live_trading_enabled": False,
            },
        )

    def intent(
        self,
        position: ManagedPaperPosition,
        assessment: PositionExitAssessment,
    ) -> PositionExitOrderIntent:
        if assessment.action != "EXIT" or not assessment.allowed:
            raise ValueError("position is not approved for exit")

        side = "SELL" if position.direction.upper() == "LONG" else "BUY"
        offset = self.policy.limit_offset_pct / 100.0
        market = float(position.current_price)
        limit_price = (
            market * (1.0 - offset)
            if side == "SELL"
            else market * (1.0 + offset)
        )
        asset_class = (
            "OPTION"
            if position.security_type.upper() in {"OPT", "OPTION"}
            else "EQUITY"
        )
        intent_id = _stable(
            "M51-EXIT",
            position.portfolio_id,
            position.position_id,
            assessment.trigger,
            position.quantity,
        )
        return PositionExitOrderIntent(
            intent_id=intent_id,
            position_id=position.position_id,
            portfolio_id=position.portfolio_id,
            symbol=position.symbol,
            asset_class=asset_class,
            side=side,
            quantity=float(position.quantity),
            order_type=self.policy.exit_order_type,
            time_in_force=self.policy.time_in_force,
            limit_price=round(limit_price, 8),
            expiry=position.expiry,
            strike=position.strike,
            right=position.right,
            local_symbol=position.local_symbol,
            contract_id=position.contract_id,
            currency=position.currency,
            reason=assessment.trigger,
            metadata={
                **position.metadata,
                "source_position_id": position.position_id,
                "source_aggregate_id": position.aggregate_id,
                "unrealized_pnl": assessment.unrealized_pnl,
                "unrealized_return_pct": assessment.unrealized_return_pct,
                "paper_only": True,
                "live_trading_enabled": False,
            },
        )

    def evaluate(
        self,
        positions: Iterable[ManagedPaperPosition],
        *,
        now: datetime | None = None,
    ) -> tuple[
        tuple[PositionExitAssessment, ...],
        tuple[PositionExitOrderIntent, ...],
    ]:
        assessments: list[PositionExitAssessment] = []
        intents: list[PositionExitOrderIntent] = []
        for position in positions:
            assessment = self.assess(position, now=now)
            assessments.append(assessment)
            if assessment.action == "EXIT" and assessment.allowed:
                intents.append(self.intent(position, assessment))
        return tuple(assessments), tuple(intents)
