from __future__ import annotations

from .options_risk_profile import OptionGreekProfile, ScenarioShockProfile
from .options_risk_service import OptionsRiskService
from .portfolio_risk_profile import PortfolioSnapshotProfile
from .portfolio_risk_service import PortfolioRiskService
from .pretrade_risk_profile import (
    PreTradeAccountProfile,
    PreTradeRiskRequest,
)
from .pretrade_risk_service import PreTradeRiskService
from .trading_control_engine import TradingControlEngine
from .trading_control_profile import (
    CombinedRiskGatewayDecision,
    TradingControlState,
    TradingSessionRiskProfile,
)


class RiskGatewayService:
    """Compose all Phase 5 risk decisions into one blocking decision."""

    def __init__(
        self,
        *,
        order_risk_service: PreTradeRiskService | None = None,
        portfolio_risk_service: PortfolioRiskService | None = None,
        options_risk_service: OptionsRiskService | None = None,
        trading_control_engine: TradingControlEngine | None = None,
    ) -> None:
        self.order_risk_service = (
            order_risk_service or PreTradeRiskService()
        )
        self.portfolio_risk_service = (
            portfolio_risk_service or PortfolioRiskService()
        )
        self.options_risk_service = (
            options_risk_service or OptionsRiskService()
        )
        self.trading_control_engine = (
            trading_control_engine or TradingControlEngine()
        )

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
        *,
        order: PreTradeRiskRequest,
        account: PreTradeAccountProfile,
        portfolio_snapshot: PortfolioSnapshotProfile,
        session: TradingSessionRiskProfile,
        control_state: TradingControlState,
        greek_legs: tuple[OptionGreekProfile, ...] = (),
        scenarios: tuple[ScenarioShockProfile, ...] | None = None,
    ) -> CombinedRiskGatewayDecision:
        order_decision = self.order_risk_service.evaluate(order, account)
        portfolio_decision = self.portfolio_risk_service.evaluate(
            order,
            portfolio_snapshot,
        )

        has_options = any(
            leg.asset_class.upper() == "OPTION"
            for leg in order.legs
        )
        options_decision = (
            self.options_risk_service.evaluate(
                order,
                account,
                greek_legs,
                scenarios,
            )
            if has_options
            else None
        )
        control_decision = self.trading_control_engine.evaluate(
            order,
            session,
            control_state,
        )

        decisions = [
            order_decision,
            portfolio_decision,
            control_decision,
        ]
        if options_decision is not None:
            decisions.append(options_decision)

        allowed = all(decision.allowed for decision in decisions)
        score = min(decision.score for decision in decisions)
        grade, severity = self._grade(score)

        rejection_reasons = tuple(
            f"{type(decision).__name__}:{reason}"
            for decision in decisions
            for reason in decision.rejection_reasons
        )
        warnings = tuple(
            f"{type(decision).__name__}:{warning}"
            for decision in decisions
            for warning in decision.warnings
        )

        return CombinedRiskGatewayDecision(
            valid=True,
            allowed=allowed,
            aggregate_id=order.aggregate_id,
            client_order_id=order.client_order_id,
            account_id=order.account_id,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="APPROVE" if allowed else "BLOCK",
            order_level_decision=order_decision,
            portfolio_decision=portfolio_decision,
            options_decision=options_decision,
            trading_control_decision=control_decision,
            rejection_reasons=rejection_reasons,
            warnings=warnings,
            metadata={
                "decision_count": len(decisions),
                "blocking_components": tuple(
                    type(decision).__name__
                    for decision in decisions
                    if not decision.allowed
                ),
            },
        )
