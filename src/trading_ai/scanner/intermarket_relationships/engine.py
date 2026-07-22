from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from .contracts import (
    IntermarketGovernanceStatus,
    IntermarketRelationshipProfile,
)
from .policy import IntermarketRelationshipPolicy


class IntermarketRelationshipEngine:
    def __init__(
        self,
        policy: IntermarketRelationshipPolicy | None = None,
    ) -> None:
        self.policy = policy or IntermarketRelationshipPolicy()

    def evaluate(
        self,
        *,
        as_of_date: date,
        features_by_symbol: Mapping[str, Mapping[str, Any]],
    ) -> IntermarketRelationshipProfile:
        spy = self._return(features_by_symbol, "SPY")
        qqq = self._return(features_by_symbol, "QQQ")
        iwm = self._return(features_by_symbol, "IWM")
        vix = self._return(features_by_symbol, "^VIX")
        ief = self._return(features_by_symbol, "IEF")
        tlt = self._return(features_by_symbol, "TLT")
        lqd = self._return(features_by_symbol, "LQD")
        hyg = self._return(features_by_symbol, "HYG")
        uup = self._return(features_by_symbol, "UUP")
        gld = self._return(features_by_symbol, "GLD")
        uso = self._return(features_by_symbol, "USO")

        growth_rs = self._spread(qqq, spy)
        small_cap_rs = self._spread(iwm, spy)
        equity_volatility = self._spread(spy, vix)
        long_duration_rs = self._spread(tlt, ief)
        equity_treasury = self._spread(spy, ief)
        credit_risk = self._spread(hyg, lqd)
        equity_dollar = self._spread(spy, uup)
        equity_gold = self._spread(spy, gld)
        equity_oil = self._spread(spy, uso)

        signals: list[float] = []

        if spy is not None:
            signals.append(1.0 if spy > self.policy.equity_positive_threshold else -1.0)

        if growth_rs is not None:
            signals.append(1.0 if growth_rs > self.policy.relative_strength_threshold else -1.0)

        if small_cap_rs is not None:
            signals.append(1.0 if small_cap_rs > self.policy.relative_strength_threshold else -1.0)

        if vix is not None:
            if vix >= self.policy.volatility_risk_off_threshold:
                signals.append(-self.policy.strong_signal_weight)
            elif vix < 0:
                signals.append(self.policy.positive_signal_weight)
            else:
                signals.append(0.0)

        if credit_risk is not None:
            signals.append(
                self.policy.strong_signal_weight
                if credit_risk > self.policy.credit_risk_on_threshold
                else -self.policy.strong_signal_weight
            )

        if equity_treasury is not None:
            signals.append(1.0 if equity_treasury > 0 else -1.0)

        if uup is not None:
            if uup >= self.policy.dollar_headwind_threshold:
                signals.append(-1.0)
            elif uup < 0:
                signals.append(0.5)
            else:
                signals.append(0.0)

        if equity_gold is not None:
            signals.append(0.5 if equity_gold > 0 else -0.5)

        if equity_oil is not None:
            signals.append(0.5 if equity_oil > 0 else -0.5)

        available = len(signals)
        status, reasons = self._govern(available)

        max_abs = sum(abs(value) for value in signals)
        net = sum(signals)
        normalized = net / max_abs if max_abs else 0.0

        risk_on_score = max(0.0, normalized)
        risk_off_score = max(0.0, -normalized)

        if normalized >= self.policy.risk_on_state_threshold:
            market_state = "RISK_ON"
        elif normalized <= self.policy.risk_off_state_threshold:
            market_state = "RISK_OFF"
        else:
            market_state = "NEUTRAL"

        completeness = min(
            1.0,
            available / self.policy.minimum_required_relationships_ready,
        )
        directional_conviction = min(1.0, abs(normalized))
        confidence = completeness * directional_conviction

        return IntermarketRelationshipProfile(
            as_of_date=as_of_date,
            equity_return_21d=spy,
            growth_relative_strength_21d=growth_rs,
            small_cap_relative_strength_21d=small_cap_rs,
            volatility_return_21d=vix,
            equity_volatility_spread=equity_volatility,
            treasury_return_21d=ief,
            long_duration_relative_strength_21d=long_duration_rs,
            equity_treasury_spread=equity_treasury,
            investment_grade_return_21d=lqd,
            high_yield_return_21d=hyg,
            credit_risk_spread=credit_risk,
            dollar_return_21d=uup,
            gold_return_21d=gld,
            oil_return_21d=uso,
            equity_dollar_spread=equity_dollar,
            equity_gold_spread=equity_gold,
            equity_oil_spread=equity_oil,
            risk_on_score=risk_on_score,
            risk_off_score=risk_off_score,
            market_state=market_state,
            confidence=confidence,
            governance_status=status,
            governance_reasons=tuple(reasons),
        )

    def _govern(
        self,
        available_relationships: int,
    ) -> tuple[IntermarketGovernanceStatus, list[str]]:
        if (
            available_relationships
            < self.policy.minimum_required_relationships_review
        ):
            return (
                IntermarketGovernanceStatus.EXCLUDED,
                [
                    f"available relationships {available_relationships} < "
                    f"{self.policy.minimum_required_relationships_review}"
                ],
            )

        if (
            available_relationships
            < self.policy.minimum_required_relationships_ready
        ):
            return (
                IntermarketGovernanceStatus.REVIEW,
                [
                    f"available relationships {available_relationships} < "
                    f"{self.policy.minimum_required_relationships_ready}"
                ],
            )

        return IntermarketGovernanceStatus.READY, []

    @staticmethod
    def _return(
        features_by_symbol: Mapping[str, Mapping[str, Any]],
        symbol: str,
    ) -> float | None:
        record = features_by_symbol.get(symbol)
        if not record:
            return None

        if record.get("governance_status") == "EXCLUDED":
            return None

        value = record.get("return_21d")
        return float(value) if value is not None else None

    @staticmethod
    def _spread(
        left: float | None,
        right: float | None,
    ) -> float | None:
        if left is None or right is None:
            return None
        return left - right
