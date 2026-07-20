from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .pretrade_governance_policy import PreTradeGovernancePolicy
from .pretrade_governance_profile import (
    ApprovalChainEntryProfile,
    GovernanceAuditRecordProfile,
    GovernanceDecisionProfile,
    GovernanceOverrideProfile,
    GovernanceRuleResultProfile,
)


class PreTradeGovernanceEngine:
    def __init__(
        self,
        policy: PreTradeGovernancePolicy | None = None,
    ) -> None:
        self.policy = policy or PreTradeGovernancePolicy()
        self.policy.validate()

    @staticmethod
    def _get(source: Any, name: str, default: Any = None) -> Any:
        if source is None:
            return default
        if isinstance(source, Mapping):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    @staticmethod
    def _severity(
        blockers: int,
        errors: int,
        warnings: int,
    ) -> str:
        if blockers >= 2:
            return "CRITICAL"
        if blockers == 1 or errors >= 2:
            return "HIGH"
        if errors == 1 or warnings >= 3:
            return "MODERATE"
        if warnings:
            return "LOW"
        return "NONE"

    def _rule(
        self,
        *,
        rule_id: str,
        rule_group: str,
        name: str,
        passed: bool,
        severity: str,
        actual: Any,
        threshold: Any,
        message: str,
        remediation: str,
        blocking: bool,
    ) -> GovernanceRuleResultProfile:
        return GovernanceRuleResultProfile(
            rule_id=rule_id,
            rule_group=rule_group,
            name=name,
            passed=bool(passed),
            severity=severity,
            actual_value=str(actual),
            threshold_value=str(threshold),
            message=message,
            remediation=remediation,
            blocking=blocking,
        )

    def evaluate(
        self,
        *,
        trade_id: str,
        symbol: str,
        strategy_name: str,
        trade_construction: Any,
        portfolio_allocation: Any,
        lifecycle: Any,
        broker_ready: bool,
        compliance_cleared: bool,
        event_risk_present: bool = False,
        override_requested: bool = False,
        override_approved: bool = False,
        override_reviewer: str | None = None,
        override_reason: str | None = None,
        override_scope: tuple[str, ...] = (),
        evaluated_at: datetime | None = None,
    ) -> GovernanceDecisionProfile:
        now = evaluated_at or datetime.now(timezone.utc)

        blueprint = self._get(trade_construction, "blueprint")
        capital = self._get(trade_construction, "capital")
        construction_ticket = self._get(trade_construction, "ticket")

        exposure = self._get(portfolio_allocation, "exposure")
        health = self._get(portfolio_allocation, "health")

        entry = self._get(lifecycle, "entry")

        construction_score = float(
            self._get(trade_construction, "construction_score", 0.0)
        )
        construction_allowed = bool(
            self._get(trade_construction, "allowed", False)
        )
        ticket_executable = bool(
            self._get(construction_ticket, "executable", False)
        )
        defined_risk = bool(
            self._get(blueprint, "defined_risk", False)
        )
        probability_of_profit = float(
            self._get(blueprint, "probability_of_profit", 0.0)
        )
        reward_risk_ratio = float(
            self._get(blueprint, "reward_risk_ratio", 0.0)
        )
        position_risk_pct = float(
            self._get(capital, "position_risk_pct", 1.0)
        )

        portfolio_allowed = bool(
            self._get(portfolio_allocation, "allowed", False)
        )
        portfolio_health_score = float(
            self._get(health, "portfolio_health_score", 0.0)
        )
        portfolio_risk_pct = float(
            self._get(health, "portfolio_risk_pct", 1.0)
        )
        buying_power_pct = float(
            self._get(health, "capital_utilization_pct", 1.0)
        )
        portfolio_delta = abs(
            float(self._get(exposure, "portfolio_delta", 0.0))
        )
        portfolio_gamma = abs(
            float(self._get(exposure, "portfolio_gamma", 0.0))
        )
        portfolio_vega = abs(
            float(self._get(exposure, "portfolio_vega", 0.0))
        )

        lifecycle_score = float(
            self._get(lifecycle, "lifecycle_score", 0.0)
        )
        lifecycle_allowed = bool(
            self._get(lifecycle, "allowed", False)
        )
        entry_allowed = bool(
            self._get(entry, "entry_allowed", False)
        )

        legs = tuple(self._get(blueprint, "legs", ()) or ())
        worst_spread = max(
            (
                float(self._get(leg, "spread_pct", 1.0))
                for leg in legs
            ),
            default=1.0,
        )
        minimum_open_interest = min(
            (
                int(self._get(leg, "open_interest", 0))
                for leg in legs
            ),
            default=0,
        )
        minimum_volume = min(
            (
                int(self._get(leg, "volume", 0))
                for leg in legs
            ),
            default=0,
        )

        rules = (
            self._rule(
                rule_id="TC-001",
                rule_group="TRADE_CONSTRUCTION",
                name="Construction Allowed",
                passed=construction_allowed,
                severity="ERROR",
                actual=construction_allowed,
                threshold=True,
                message="Trade construction must be allowed.",
                remediation="Resolve construction rejection reasons.",
                blocking=True,
            ),
            self._rule(
                rule_id="TC-002",
                rule_group="TRADE_CONSTRUCTION",
                name="Construction Score",
                passed=(
                    construction_score
                    >= self.policy.minimum_trade_construction_score
                ),
                severity="WARNING",
                actual=f"{construction_score:.2f}",
                threshold=(
                    f">={self.policy.minimum_trade_construction_score:.2f}"
                ),
                message="Construction score must meet policy.",
                remediation="Improve payoff, liquidity, or risk structure.",
                blocking=False,
            ),
            self._rule(
                rule_id="TC-003",
                rule_group="TRADE_CONSTRUCTION",
                name="Executable Ticket",
                passed=ticket_executable,
                severity="ERROR",
                actual=ticket_executable,
                threshold=True,
                message="Trade ticket must be executable.",
                remediation="Correct ticket sizing or construction blockers.",
                blocking=True,
            ),
            self._rule(
                rule_id="RK-001",
                rule_group="RISK",
                name="Defined Risk",
                passed=(
                    defined_risk
                    or not self.policy.require_defined_risk
                ),
                severity="ERROR",
                actual=defined_risk,
                threshold=self.policy.require_defined_risk,
                message="Defined-risk structure is required.",
                remediation="Convert to a bounded-risk spread.",
                blocking=True,
            ),
            self._rule(
                rule_id="RK-002",
                rule_group="RISK",
                name="Position Risk",
                passed=(
                    position_risk_pct
                    <= self.policy.maximum_position_risk_pct
                ),
                severity="ERROR",
                actual=f"{position_risk_pct:.4f}",
                threshold=(
                    f"<={self.policy.maximum_position_risk_pct:.4f}"
                ),
                message="Position risk must fit policy.",
                remediation="Reduce contracts or maximum loss.",
                blocking=True,
            ),
            self._rule(
                rule_id="AN-001",
                rule_group="ANALYTICS",
                name="Probability of Profit",
                passed=(
                    probability_of_profit
                    >= self.policy.minimum_probability_of_profit
                ),
                severity="WARNING",
                actual=f"{probability_of_profit:.4f}",
                threshold=(
                    f">={self.policy.minimum_probability_of_profit:.4f}"
                ),
                message="Probability of profit is below policy.",
                remediation="Select a higher-probability structure.",
                blocking=False,
            ),
            self._rule(
                rule_id="AN-002",
                rule_group="ANALYTICS",
                name="Reward Risk",
                passed=(
                    reward_risk_ratio
                    >= self.policy.minimum_reward_risk_ratio
                ),
                severity="WARNING",
                actual=f"{reward_risk_ratio:.4f}",
                threshold=(
                    f">={self.policy.minimum_reward_risk_ratio:.4f}"
                ),
                message="Reward/risk is below policy.",
                remediation="Improve strike selection or entry pricing.",
                blocking=False,
            ),
            self._rule(
                rule_id="PF-001",
                rule_group="PORTFOLIO",
                name="Portfolio Allocation Allowed",
                passed=portfolio_allowed,
                severity="ERROR",
                actual=portfolio_allowed,
                threshold=True,
                message="Portfolio allocation must be allowed.",
                remediation="Resolve allocation rejections.",
                blocking=True,
            ),
            self._rule(
                rule_id="PF-002",
                rule_group="PORTFOLIO",
                name="Portfolio Health",
                passed=(
                    portfolio_health_score
                    >= self.policy.minimum_portfolio_health_score
                ),
                severity="WARNING",
                actual=f"{portfolio_health_score:.2f}",
                threshold=(
                    f">={self.policy.minimum_portfolio_health_score:.2f}"
                ),
                message="Portfolio health is below policy target.",
                remediation="Improve diversification or liquidity.",
                blocking=False,
            ),
            self._rule(
                rule_id="PF-003",
                rule_group="PORTFOLIO",
                name="Portfolio Risk",
                passed=(
                    portfolio_risk_pct
                    <= self.policy.maximum_portfolio_risk_pct
                ),
                severity="ERROR",
                actual=f"{portfolio_risk_pct:.4f}",
                threshold=(
                    f"<={self.policy.maximum_portfolio_risk_pct:.4f}"
                ),
                message="Portfolio risk exceeds policy.",
                remediation="Reduce aggregate portfolio risk.",
                blocking=True,
            ),
            self._rule(
                rule_id="PF-004",
                rule_group="PORTFOLIO",
                name="Buying Power",
                passed=(
                    buying_power_pct
                    <= self.policy.maximum_buying_power_pct
                ),
                severity="ERROR",
                actual=f"{buying_power_pct:.4f}",
                threshold=(
                    f"<={self.policy.maximum_buying_power_pct:.4f}"
                ),
                message="Buying-power utilization exceeds policy.",
                remediation="Reduce allocation or free buying power.",
                blocking=True,
            ),
            self._rule(
                rule_id="GX-001",
                rule_group="GREEKS",
                name="Portfolio Delta",
                passed=(
                    portfolio_delta
                    <= self.policy.maximum_abs_portfolio_delta
                ),
                severity="WARNING",
                actual=f"{portfolio_delta:.2f}",
                threshold=(
                    f"<={self.policy.maximum_abs_portfolio_delta:.2f}"
                ),
                message="Portfolio delta exceeds policy.",
                remediation="Hedge or reduce directional exposure.",
                blocking=False,
            ),
            self._rule(
                rule_id="GX-002",
                rule_group="GREEKS",
                name="Portfolio Gamma",
                passed=(
                    portfolio_gamma
                    <= self.policy.maximum_abs_portfolio_gamma
                ),
                severity="WARNING",
                actual=f"{portfolio_gamma:.2f}",
                threshold=(
                    f"<={self.policy.maximum_abs_portfolio_gamma:.2f}"
                ),
                message="Portfolio gamma exceeds policy.",
                remediation="Reduce short-gamma exposure.",
                blocking=False,
            ),
            self._rule(
                rule_id="GX-003",
                rule_group="GREEKS",
                name="Portfolio Vega",
                passed=(
                    portfolio_vega
                    <= self.policy.maximum_abs_portfolio_vega
                ),
                severity="WARNING",
                actual=f"{portfolio_vega:.2f}",
                threshold=(
                    f"<={self.policy.maximum_abs_portfolio_vega:.2f}"
                ),
                message="Portfolio vega exceeds policy.",
                remediation="Reduce volatility concentration.",
                blocking=False,
            ),
            self._rule(
                rule_id="LQ-001",
                rule_group="LIQUIDITY",
                name="Bid Ask Spread",
                passed=(
                    worst_spread
                    <= self.policy.maximum_bid_ask_spread_pct
                ),
                severity="WARNING",
                actual=f"{worst_spread:.4f}",
                threshold=(
                    f"<={self.policy.maximum_bid_ask_spread_pct:.4f}"
                ),
                message="Option spread exceeds policy.",
                remediation="Select a more liquid contract.",
                blocking=False,
            ),
            self._rule(
                rule_id="LQ-002",
                rule_group="LIQUIDITY",
                name="Open Interest",
                passed=(
                    minimum_open_interest
                    >= self.policy.minimum_open_interest
                ),
                severity="WARNING",
                actual=minimum_open_interest,
                threshold=f">={self.policy.minimum_open_interest}",
                message="Open interest is below policy.",
                remediation="Select a more liquid strike or expiry.",
                blocking=False,
            ),
            self._rule(
                rule_id="LQ-003",
                rule_group="LIQUIDITY",
                name="Option Volume",
                passed=(
                    minimum_volume
                    >= self.policy.minimum_option_volume
                ),
                severity="WARNING",
                actual=minimum_volume,
                threshold=f">={self.policy.minimum_option_volume}",
                message="Option volume is below policy.",
                remediation="Select a contract with stronger volume.",
                blocking=False,
            ),
            self._rule(
                rule_id="LC-001",
                rule_group="LIFECYCLE",
                name="Lifecycle Ready",
                passed=(
                    lifecycle_allowed
                    and entry_allowed
                    or not self.policy.require_lifecycle_ready
                ),
                severity="ERROR",
                actual=(
                    lifecycle_allowed and entry_allowed
                ),
                threshold=self.policy.require_lifecycle_ready,
                message="Lifecycle and entry plans must be ready.",
                remediation="Resolve lifecycle blockers.",
                blocking=True,
            ),
            self._rule(
                rule_id="LC-002",
                rule_group="LIFECYCLE",
                name="Lifecycle Score",
                passed=(
                    lifecycle_score
                    >= self.policy.minimum_lifecycle_score
                ),
                severity="WARNING",
                actual=f"{lifecycle_score:.2f}",
                threshold=(
                    f">={self.policy.minimum_lifecycle_score:.2f}"
                ),
                message="Lifecycle score is below policy.",
                remediation="Strengthen entry, exit, and adjustment planning.",
                blocking=False,
            ),
            self._rule(
                rule_id="EV-001",
                rule_group="EVENT_RISK",
                name="Event Risk",
                passed=not event_risk_present,
                severity="WARNING",
                actual=event_risk_present,
                threshold=False,
                message="Material event risk is present.",
                remediation="Hedge, reduce, defer, or approve event exposure.",
                blocking=False,
            ),
            self._rule(
                rule_id="BR-001",
                rule_group="BROKER",
                name="Broker Readiness",
                passed=(
                    broker_ready
                    or not self.policy.require_broker_ready
                ),
                severity="ERROR",
                actual=broker_ready,
                threshold=self.policy.require_broker_ready,
                message="Broker connection and account are not ready.",
                remediation="Restore broker operational readiness.",
                blocking=True,
            ),
            self._rule(
                rule_id="CP-001",
                rule_group="COMPLIANCE",
                name="Compliance Clearance",
                passed=(
                    compliance_cleared
                    or not self.policy.require_compliance_clearance
                ),
                severity="ERROR",
                actual=compliance_cleared,
                threshold=self.policy.require_compliance_clearance,
                message="Compliance clearance is required.",
                remediation="Resolve compliance restrictions.",
                blocking=True,
            ),
        )

        override = GovernanceOverrideProfile(
            requested=override_requested,
            approved=override_approved,
            reviewer=override_reviewer,
            reason=override_reason,
            scope=tuple(override_scope),
        )

        effective_failures = []
        for rule in rules:
            if rule.passed:
                continue
            if (
                override.approved
                and rule.rule_id in override.scope
                and rule.rule_group != "COMPLIANCE"
            ):
                continue
            effective_failures.append(rule)

        blocking_failures = [
            rule for rule in effective_failures
            if rule.blocking
        ]
        error_failures = [
            rule for rule in effective_failures
            if rule.severity == "ERROR"
        ]
        warning_failures = [
            rule for rule in effective_failures
            if rule.severity == "WARNING"
        ]

        rule_weights = {
            "ERROR": 6.0,
            "WARNING": 2.0,
            "INFO": 1.0,
        }
        deduction = sum(
            rule_weights.get(rule.severity, 1.0)
            for rule in effective_failures
        )
        score = max(0.0, round(100.0 - deduction, 6))
        confidence_score = round(
            (
                construction_score
                + portfolio_health_score
                + lifecycle_score
            )
            / 3.0,
            6,
        )

        warnings = tuple(
            dict.fromkeys(
                rule.message
                for rule in warning_failures
            )
        )
        rejection_reasons = tuple(
            dict.fromkeys(
                rule.message
                for rule in blocking_failures
            )
        )
        remediation_actions = tuple(
            dict.fromkeys(
                rule.remediation
                for rule in effective_failures
            )
        )
        residual_risks = tuple(
            dict.fromkeys(
                rule.name
                for rule in rules
                if not rule.passed
            )
        )
        positive_factors = tuple(
            dict.fromkeys(
                rule.name
                for rule in rules
                if rule.passed
            )
        )

        if blocking_failures:
            approval_status = "REJECTED"
            recommendation = "Do not submit the trade."
            allowed = False
        elif portfolio_risk_pct >= self.policy.risk_committee_risk_pct:
            approval_status = "RISK_COMMITTEE_APPROVAL"
            recommendation = (
                "Escalate to the risk committee before submission."
            )
            allowed = False
        elif position_risk_pct >= self.policy.manager_approval_risk_pct:
            approval_status = "MANAGER_APPROVAL"
            recommendation = (
                "Obtain manager approval before submission."
            )
            allowed = False
        elif (
            score >= self.policy.auto_approval_minimum_score
            and len(warning_failures)
            <= self.policy.maximum_warning_count_for_auto_approval
        ):
            approval_status = "AUTO_APPROVED"
            recommendation = "Trade may proceed automatically."
            allowed = True
        elif (
            score >= self.policy.warning_approval_minimum_score
            and len(warning_failures)
            <= self.policy.maximum_warning_count_for_warning_approval
        ):
            approval_status = "APPROVED_WITH_WARNINGS"
            recommendation = (
                "Trade may proceed with documented warnings."
            )
            allowed = True
        elif score >= self.policy.manager_approval_minimum_score:
            approval_status = "REQUIRES_REVIEW"
            recommendation = (
                "Manual review is required before submission."
            )
            allowed = False
        else:
            approval_status = "REJECTED"
            recommendation = "Do not submit the trade."
            allowed = False

        approval_chain = (
            ApprovalChainEntryProfile(
                level="AUTOMATED_GOVERNANCE",
                required=True,
                status="COMPLETE",
                reviewer_role="SYSTEM",
                rationale="Rule evaluation and scoring completed.",
            ),
            ApprovalChainEntryProfile(
                level="MANAGER",
                required=approval_status == "MANAGER_APPROVAL",
                status=(
                    "PENDING"
                    if approval_status == "MANAGER_APPROVAL"
                    else "NOT_REQUIRED"
                ),
                reviewer_role="PORTFOLIO_MANAGER",
                rationale="Required for elevated position risk.",
            ),
            ApprovalChainEntryProfile(
                level="RISK_COMMITTEE",
                required=(
                    approval_status == "RISK_COMMITTEE_APPROVAL"
                ),
                status=(
                    "PENDING"
                    if approval_status == "RISK_COMMITTEE_APPROVAL"
                    else "NOT_REQUIRED"
                ),
                reviewer_role="RISK_COMMITTEE",
                rationale="Required for elevated portfolio risk.",
            ),
        )

        audit_trail = tuple(
            GovernanceAuditRecordProfile(
                timestamp=now,
                rule_id=rule.rule_id,
                outcome="PASS" if rule.passed else "FAIL",
                actual_value=rule.actual_value,
                threshold_value=rule.threshold_value,
                source_component=rule.rule_group,
                reviewer=(
                    override.reviewer
                    if (
                        override.approved
                        and rule.rule_id in override.scope
                    )
                    else None
                ),
                notes=(
                    override.reason
                    if (
                        override.approved
                        and rule.rule_id in override.scope
                    )
                    else None
                ),
            )
            for rule in rules
        )

        return GovernanceDecisionProfile(
            trade_id=trade_id,
            symbol=symbol,
            strategy_name=strategy_name,
            governance_score=score,
            governance_grade=self._grade(score),
            confidence_score=confidence_score,
            risk_severity=self._severity(
                len(blocking_failures),
                len(error_failures),
                len(warning_failures),
            ),
            approval_status=approval_status,
            approval_recommendation=recommendation,
            allowed=allowed,
            rules=rules,
            audit_trail=audit_trail,
            approval_chain=approval_chain,
            override=override,
            positive_factors=positive_factors,
            residual_risks=residual_risks,
            remediation_actions=remediation_actions,
            warnings=warnings,
            rejection_reasons=rejection_reasons,
            metadata={
                "milestone": 34,
                "phase": 3,
                "step": 4,
                "source": "PRETRADE_GOVERNANCE_APPROVAL",
                "evaluated_at": now.isoformat(),
            },
        )
