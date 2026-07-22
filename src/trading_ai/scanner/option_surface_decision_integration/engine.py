from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from .contracts import (
    SurfaceDecisionFeatureProfile,
    SurfaceDecisionPolicy,
    SurfaceDecisionStatus,
)


class OptionSurfaceDecisionEngine:
    def __init__(
        self,
        policy: SurfaceDecisionPolicy | None = None,
    ) -> None:
        self.policy = policy or SurfaceDecisionPolicy()

    def evaluate(
        self,
        row: Mapping[str, Any],
    ) -> SurfaceDecisionFeatureProfile:
        symbol = str(row["underlying_symbol"]).strip().upper()
        quote_date = self._to_date(row["quote_date"])
        surface_status = str(
            row.get("governance_status", "UNKNOWN")
        ).strip().upper()

        expiration_count = self._int(row.get("expiration_count"))
        total_contract_count = self._int(
            row.get("total_contract_count")
        )
        total_volume = self._int(row.get("total_volume"))
        total_open_interest = self._int(
            row.get("total_open_interest")
        )

        nearest_atm_iv = self._float_or_none(
            row.get("nearest_atm_implied_volatility")
        )
        farthest_atm_iv = self._float_or_none(
            row.get("farthest_atm_implied_volatility")
        )
        term_slope = self._float_or_none(
            row.get("atm_term_structure_slope")
        )
        put_call_volume = self._float_or_none(
            row.get("aggregate_put_call_volume_ratio")
        )
        put_call_oi = self._float_or_none(
            row.get("aggregate_put_call_open_interest_ratio")
        )

        reasons: list[str] = []
        decision_status = SurfaceDecisionStatus.ELIGIBLE

        if (
            surface_status
            not in self.policy.normalized_allowed_statuses()
        ):
            decision_status = SurfaceDecisionStatus.BLOCKED
            reasons.append(
                f"surface governance status {surface_status} is not allowed"
            )

        if expiration_count < self.policy.minimum_expiration_count:
            decision_status = SurfaceDecisionStatus.BLOCKED
            reasons.append(
                f"expiration count {expiration_count} < "
                f"{self.policy.minimum_expiration_count}"
            )

        if total_open_interest < self.policy.minimum_total_open_interest:
            if self.policy.block_missing_liquidity:
                decision_status = SurfaceDecisionStatus.BLOCKED
            elif decision_status != SurfaceDecisionStatus.BLOCKED:
                decision_status = SurfaceDecisionStatus.REVIEW
            reasons.append(
                f"open interest {total_open_interest} < "
                f"{self.policy.minimum_total_open_interest}"
            )

        if total_volume < self.policy.minimum_total_volume:
            if self.policy.block_missing_liquidity:
                decision_status = SurfaceDecisionStatus.BLOCKED
            elif decision_status != SurfaceDecisionStatus.BLOCKED:
                decision_status = SurfaceDecisionStatus.REVIEW
            reasons.append(
                f"volume {total_volume} < "
                f"{self.policy.minimum_total_volume}"
            )

        if term_slope is None:
            if (
                self.policy.review_missing_term_structure
                and decision_status
                != SurfaceDecisionStatus.BLOCKED
            ):
                decision_status = SurfaceDecisionStatus.REVIEW
            reasons.append("ATM term structure unavailable")
        elif (
            abs(term_slope)
            > self.policy.maximum_absolute_term_structure_slope
        ):
            if decision_status != SurfaceDecisionStatus.BLOCKED:
                decision_status = SurfaceDecisionStatus.REVIEW
            reasons.append(
                "ATM term-structure slope exceeds configured review limit"
            )

        if (
            put_call_oi is not None
            and put_call_oi
            > self.policy.maximum_put_call_open_interest_ratio
        ):
            if decision_status != SurfaceDecisionStatus.BLOCKED:
                decision_status = SurfaceDecisionStatus.REVIEW
            reasons.append(
                "put/call open-interest ratio exceeds review limit"
            )

        if (
            put_call_volume is not None
            and put_call_volume
            > self.policy.maximum_put_call_volume_ratio
        ):
            if decision_status != SurfaceDecisionStatus.BLOCKED:
                decision_status = SurfaceDecisionStatus.REVIEW
            reasons.append(
                "put/call volume ratio exceeds review limit"
            )

        iv_regime = self._term_structure_regime(term_slope)
        flow_bias = self._flow_bias(
            put_call_volume,
            put_call_oi,
        )
        liquidity_regime = self._liquidity_regime(
            total_volume,
            total_open_interest,
        )

        call_adjustment, put_adjustment = (
            self._directional_adjustments(
                iv_regime=iv_regime,
                flow_bias=flow_bias,
            )
        )

        confidence_adjustment = self._confidence_adjustment(
            decision_status=decision_status,
            liquidity_regime=liquidity_regime,
            term_slope=term_slope,
        )

        return SurfaceDecisionFeatureProfile(
            underlying_symbol=symbol,
            quote_date=quote_date,
            surface_governance_status=surface_status,
            decision_status=decision_status,
            decision_reasons=tuple(reasons),
            expiration_count=expiration_count,
            total_contract_count=total_contract_count,
            total_volume=total_volume,
            total_open_interest=total_open_interest,
            nearest_atm_implied_volatility=nearest_atm_iv,
            farthest_atm_implied_volatility=farthest_atm_iv,
            atm_term_structure_slope=term_slope,
            aggregate_put_call_volume_ratio=put_call_volume,
            aggregate_put_call_open_interest_ratio=put_call_oi,
            iv_term_structure_regime=iv_regime,
            options_flow_bias=flow_bias,
            liquidity_regime=liquidity_regime,
            call_signal_adjustment=call_adjustment,
            put_signal_adjustment=put_adjustment,
            confidence_adjustment=confidence_adjustment,
        )

    @staticmethod
    def _term_structure_regime(
        slope: float | None,
    ) -> str:
        if slope is None:
            return "NOT_OBSERVED"
        if slope > 0.0005:
            return "CONTANGO"
        if slope < -0.0005:
            return "BACKWARDATION"
        return "FLAT"

    @staticmethod
    def _flow_bias(
        put_call_volume: float | None,
        put_call_oi: float | None,
    ) -> str:
        observed = [
            value
            for value in (put_call_volume, put_call_oi)
            if value is not None
        ]
        if not observed:
            return "NOT_OBSERVED"

        average = sum(observed) / len(observed)
        if average >= 1.25:
            return "PUT_BIASED"
        if average <= 0.80:
            return "CALL_BIASED"
        return "BALANCED"

    def _liquidity_regime(
        self,
        volume: int,
        open_interest: int,
    ) -> str:
        if (
            volume >= self.policy.minimum_total_volume * 10
            and open_interest
            >= self.policy.minimum_total_open_interest * 10
        ):
            return "DEEP"
        if (
            volume >= self.policy.minimum_total_volume
            and open_interest
            >= self.policy.minimum_total_open_interest
        ):
            return "ADEQUATE"
        return "THIN"

    @staticmethod
    def _directional_adjustments(
        *,
        iv_regime: str,
        flow_bias: str,
    ) -> tuple[float, float]:
        call_adjustment = 0.0
        put_adjustment = 0.0

        if flow_bias == "CALL_BIASED":
            call_adjustment += 0.05
            put_adjustment -= 0.03
        elif flow_bias == "PUT_BIASED":
            put_adjustment += 0.05
            call_adjustment -= 0.03

        if iv_regime == "BACKWARDATION":
            put_adjustment += 0.02
            call_adjustment -= 0.01
        elif iv_regime == "CONTANGO":
            call_adjustment += 0.01

        return (
            round(call_adjustment, 8),
            round(put_adjustment, 8),
        )

    @staticmethod
    def _confidence_adjustment(
        *,
        decision_status: SurfaceDecisionStatus,
        liquidity_regime: str,
        term_slope: float | None,
    ) -> float:
        if decision_status == SurfaceDecisionStatus.BLOCKED:
            return -1.0

        adjustment = 0.0
        if liquidity_regime == "DEEP":
            adjustment += 0.05
        elif liquidity_regime == "THIN":
            adjustment -= 0.10

        if term_slope is None:
            adjustment -= 0.05

        if decision_status == SurfaceDecisionStatus.REVIEW:
            adjustment -= 0.10

        return round(adjustment, 8)

    @staticmethod
    def _to_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _int(value: Any) -> int:
        if value in (None, ""):
            return 0
        return int(float(value))

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        if value in (None, ""):
            return None
        return float(value)
