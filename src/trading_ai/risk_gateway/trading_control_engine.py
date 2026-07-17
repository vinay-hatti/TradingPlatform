from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .pretrade_risk_profile import PreTradeRiskRequest
from .trading_control_policy import TradingControlPolicy
from .trading_control_profile import (
    TradingControlCheck,
    TradingControlDecision,
    TradingControlState,
    TradingSessionRiskProfile,
)


class TradingControlEngine:
    def __init__(self, policy: TradingControlPolicy | None = None) -> None:
        self.policy = policy or TradingControlPolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    @staticmethod
    def _is_reduce_only(order: PreTradeRiskRequest) -> bool:
        return bool(order.legs) and all(
            leg.position_effect.upper() == "CLOSE"
            or leg.side.upper().endswith("_TO_CLOSE")
            for leg in order.legs
        )

    @staticmethod
    def _active_halts(
        state: TradingControlState,
    ) -> tuple:
        now = datetime.now(timezone.utc)
        result = []
        for halt in state.halts:
            if not halt.active:
                continue
            if halt.expires_at:
                expiry = datetime.fromisoformat(
                    halt.expires_at.replace("Z", "+00:00")
                )
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= now:
                    continue
            result.append(halt)
        return tuple(result)

    def evaluate(
        self,
        order: PreTradeRiskRequest,
        session: TradingSessionRiskProfile | None,
        state: TradingControlState | None,
    ) -> TradingControlDecision:
        checks: list[TradingControlCheck] = []
        warnings: list[str] = []
        reduce_only = self._is_reduce_only(order)

        def add(
            name: str,
            passed: bool,
            message: str,
            *,
            required: bool = True,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                TradingControlCheck(
                    name=name,
                    passed=bool(passed),
                    required=required,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                    metadata=metadata or {},
                )
            )

        add(
            "control_state",
            state is not None or not self.policy.require_control_state,
            "Trading control state is available.",
            required=self.policy.require_control_state,
        )
        add(
            "session_profile",
            session is not None,
            "Trading session risk profile is available.",
        )

        active_halts = self._active_halts(state) if state is not None else ()
        account_halts = tuple(
            halt for halt in active_halts
            if halt.scope_type == "ACCOUNT"
            and halt.scope_value == order.account_id.upper()
        )
        order_symbols = {leg.symbol.upper() for leg in order.legs}
        order_sectors = {
            str(leg.metadata.get("sector", "")).upper()
            for leg in order.legs
            if leg.metadata.get("sector")
        }
        symbol_halts = tuple(
            halt for halt in active_halts
            if halt.scope_type == "SYMBOL"
            and halt.scope_value in order_symbols
        )
        sector_halts = tuple(
            halt for halt in active_halts
            if halt.scope_type == "SECTOR"
            and halt.scope_value in order_sectors
        )

        halt_override = reduce_only and self.policy.allow_reduce_only_during_halt
        if halt_override and active_halts:
            warnings.append("REDUCE_ONLY_HALT_OVERRIDE")

        if state is not None:
            add(
                "manual_kill_switch",
                (
                    not state.kill_switch.manual_active
                    or not self.policy.reject_when_manual_kill_switch_active
                    or halt_override
                ),
                "Manual kill switch is not blocking the order.",
            )
            add(
                "automatic_kill_switch",
                (
                    not state.kill_switch.automatic_active
                    or not self.policy.reject_when_automatic_kill_switch_active
                    or halt_override
                ),
                "Automatic kill switch is not blocking the order.",
            )
            add(
                "account_halt",
                (
                    not account_halts
                    or not self.policy.reject_when_account_halted
                    or halt_override
                ),
                "Account trading halt is not blocking the order.",
            )
            add(
                "symbol_halt",
                (
                    not symbol_halts
                    or not self.policy.reject_when_symbol_halted
                    or halt_override
                ),
                "Symbol trading halt is not blocking the order.",
            )
            add(
                "sector_halt",
                (
                    not sector_halts
                    or not self.policy.reject_when_sector_halted
                    or halt_override
                ),
                "Sector trading halt is not blocking the order.",
            )

        if session is not None:
            realized_loss = max(0.0, -session.daily_realized_pnl)
            total_loss = max(0.0, -session.daily_total_pnl)
            drawdown = session.intraday_drawdown
            drawdown_pct = session.drawdown_pct

            add(
                "daily_realized_loss",
                (
                    realized_loss <= self.policy.maximum_daily_realized_loss
                    or not self.policy.halt_on_daily_realized_loss
                    or halt_override
                ),
                "Daily realized loss is within policy.",
                metadata={
                    "loss": realized_loss,
                    "limit": self.policy.maximum_daily_realized_loss,
                },
            )
            add(
                "daily_total_loss",
                (
                    total_loss <= self.policy.maximum_daily_total_loss
                    or not self.policy.halt_on_daily_total_loss
                    or halt_override
                ),
                "Daily total loss is within policy.",
            )
            add(
                "intraday_drawdown",
                (
                    drawdown <= self.policy.maximum_intraday_drawdown
                    or not self.policy.halt_on_drawdown
                    or halt_override
                ),
                "Intraday drawdown is within absolute limit.",
            )
            add(
                "drawdown_pct",
                (
                    drawdown_pct is not None
                    and drawdown_pct
                    <= self.policy.maximum_drawdown_pct_of_starting_equity
                )
                or not self.policy.halt_on_drawdown
                or halt_override,
                "Intraday drawdown percentage is within policy.",
            )
            add(
                "consecutive_losing_trades",
                (
                    session.consecutive_losing_trades
                    < self.policy.maximum_consecutive_losing_trades
                    or not self.policy.halt_on_consecutive_losses
                    or halt_override
                ),
                "Consecutive losing trades are within policy.",
            )
            add(
                "rejected_orders",
                (
                    session.rejected_orders
                    < self.policy.maximum_rejected_orders_per_session
                    or not self.policy.halt_on_rejected_orders
                    or halt_override
                ),
                "Rejected-order count is within policy.",
                required=self.policy.halt_on_rejected_orders,
            )
            add(
                "risk_breaches",
                (
                    session.risk_breaches
                    < self.policy.maximum_risk_breaches_per_session
                    or not self.policy.halt_on_risk_breaches
                    or halt_override
                ),
                "Risk-breach count is within policy.",
                required=self.policy.halt_on_risk_breaches,
            )

        required_checks = [check for check in checks if check.required]
        failed = [check for check in required_checks if not check.passed]
        score = (
            sum(check.score for check in required_checks)
            / len(required_checks)
            if required_checks else 100.0
        )
        allowed = (
            not failed
            and score >= self.policy.minimum_approval_score
        )
        if not self.policy.fail_closed:
            allowed = score >= self.policy.minimum_approval_score

        grade, severity = self._grade(score)
        return TradingControlDecision(
            valid=True,
            allowed=allowed,
            account_id=order.account_id,
            aggregate_id=order.aggregate_id,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation=(
                "ALLOW_REDUCE_ONLY"
                if allowed and halt_override
                else "APPROVE"
                if allowed
                else "HALT"
            ),
            reduce_only=reduce_only,
            session=session,
            control_state=state,
            checks=tuple(checks),
            warnings=tuple(warnings),
            rejection_reasons=tuple(
                check.name.upper() for check in failed
            ),
            metadata={
                "active_halt_ids": tuple(
                    halt.halt_id for halt in active_halts
                ),
                "automatic_halt_required": bool(failed),
            },
        )
