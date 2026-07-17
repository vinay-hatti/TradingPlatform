from __future__ import annotations
from typing import Any
from .portfolio_exposure_engine import PortfolioExposureEngine
from .portfolio_risk_policy import PortfolioRiskPolicy
from .portfolio_risk_profile import PortfolioRiskCheck, PortfolioRiskDecision, PortfolioSnapshotProfile
from .position_limit_engine import PositionLimitEngine
from .pretrade_risk_profile import PreTradeRiskRequest

class PortfolioRiskEngine:
    def __init__(self, policy: PortfolioRiskPolicy | None = None) -> None:
        self.policy = policy or PortfolioRiskPolicy()
        self.policy.validate()
        self.exposure_engine = PortfolioExposureEngine(self.policy)
        self.position_limit_engine = PositionLimitEngine(self.policy)

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95: return "A", "LOW"
        if score >= 85: return "B", "MODERATE"
        if score >= 70: return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate(self, order: PreTradeRiskRequest, snapshot: PortfolioSnapshotProfile) -> PortfolioRiskDecision:
        checks = []
        def add(name, passed, message, required=True, metadata=None):
            checks.append(PortfolioRiskCheck(
                name=name, passed=bool(passed), required=required,
                score=100.0 if passed else 0.0,
                severity="LOW" if passed else "CRITICAL",
                message=message, metadata=metadata or {},
            ))

        add(
            "account_match",
            order.account_id == snapshot.account.account_id or not self.policy.require_account_match,
            "Order account matches portfolio snapshot account.",
            required=self.policy.require_account_match,
        )

        exposure = self.exposure_engine.calculate(order, snapshot)
        add("maximum_gross_exposure", exposure.projected_gross_exposure <= self.policy.maximum_gross_exposure, "Projected gross exposure is within policy.")
        add("maximum_net_exposure", abs(exposure.projected_net_exposure) <= self.policy.maximum_net_exposure_absolute, "Projected net exposure is within policy.")
        add("maximum_open_positions", exposure.projected_open_positions <= self.policy.maximum_open_positions, "Projected open-position count is within policy.")
        add("maximum_new_positions", exposure.new_positions <= self.policy.maximum_new_positions_per_order, "New positions introduced by the order are within policy.")
        add(
            "buying_power_utilization",
            exposure.projected_buying_power_utilization is not None
            and exposure.projected_buying_power_utilization <= self.policy.maximum_total_buying_power_utilization,
            "Projected buying-power utilization is within policy.",
        )
        add("post_trade_buying_power", exposure.projected_buying_power_remaining >= self.policy.minimum_post_trade_buying_power, "Projected buying power remains above minimum.")
        add("post_trade_excess_liquidity", exposure.projected_excess_liquidity >= self.policy.minimum_post_trade_excess_liquidity, "Projected excess liquidity remains above minimum.")

        for symbol in exposure.symbols:
            add(
                f"single_symbol_exposure:{symbol.symbol}",
                abs(symbol.projected_exposure) <= self.policy.maximum_single_symbol_exposure,
                "Projected symbol exposure is within absolute limit.",
            )
            add(
                f"single_symbol_concentration:{symbol.symbol}",
                symbol.pct_of_net_liquidation is not None
                and symbol.pct_of_net_liquidation <= self.policy.maximum_single_symbol_pct_of_net_liquidation,
                "Projected symbol concentration is within policy.",
                required=self.policy.reject_concentration_limit_breaches,
            )
            if self.policy.require_sector_classification:
                add(
                    f"sector_classification:{symbol.symbol}",
                    bool(symbol.sector),
                    "Sector classification is required.",
                )

        for sector in exposure.sectors:
            add(
                f"sector_exposure:{sector.sector}",
                abs(sector.projected_exposure) <= self.policy.maximum_sector_exposure,
                "Projected sector exposure is within absolute limit.",
            )
            add(
                f"sector_concentration:{sector.sector}",
                sector.pct_of_net_liquidation is not None
                and sector.pct_of_net_liquidation <= self.policy.maximum_sector_pct_of_net_liquidation,
                "Projected sector concentration is within policy.",
                required=self.policy.reject_concentration_limit_breaches,
            )

        checks.extend(self.position_limit_engine.checks(exposure, snapshot))
        required_checks = [c for c in checks if c.required]
        failed = [c for c in required_checks if not c.passed]
        score = sum(c.score for c in required_checks) / len(required_checks) if required_checks else 100.0
        allowed = not failed and score >= self.policy.minimum_approval_score
        if not self.policy.fail_closed:
            allowed = score >= self.policy.minimum_approval_score
        grade, severity = self._grade(score)

        return PortfolioRiskDecision(
            valid=True,
            allowed=allowed,
            aggregate_id=order.aggregate_id,
            client_order_id=order.client_order_id,
            account_id=order.account_id,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="APPROVE" if allowed else "REJECT",
            exposure=exposure,
            snapshot=snapshot,
            order=order,
            checks=tuple(checks),
            rejection_reasons=tuple(c.name.upper() for c in failed),
            metadata={
                "projected_open_positions": exposure.projected_open_positions,
                "new_positions": exposure.new_positions,
            },
        )
