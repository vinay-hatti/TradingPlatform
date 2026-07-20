from __future__ import annotations

from typing import Any, Mapping

from .phase3_dashboard_profile import (
    DashboardMetricProfile,
    DashboardSectionProfile,
    Phase3DashboardProfile,
)


class Phase3DashboardEngine:
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
    def _status(
        *,
        allowed: bool,
        warnings: tuple[str, ...],
        rejections: tuple[str, ...],
    ) -> str:
        if rejections:
            return "BLOCKED"
        if allowed and warnings:
            return "READY_WITH_WARNINGS"
        if allowed:
            return "READY"
        return "REVIEW_REQUIRED"

    def build(
        self,
        *,
        trade_id: str,
        symbol: str,
        strategy_name: str,
        trade_construction: Any,
        portfolio_allocation: Any,
        lifecycle: Any,
        governance: Any,
    ) -> Phase3DashboardProfile:
        construction_score = float(
            self._get(trade_construction, "construction_score", 0.0)
        )
        construction_grade = str(
            self._get(
                trade_construction,
                "construction_grade",
                self._grade(construction_score),
            )
        )
        construction_allowed = bool(
            self._get(trade_construction, "allowed", False)
        )
        construction_warnings = tuple(
            self._get(trade_construction, "warnings", ()) or ()
        )
        construction_rejections = tuple(
            self._get(
                trade_construction, "rejection_reasons", ()
            ) or ()
        )

        ticket = self._get(trade_construction, "ticket")
        capital = self._get(trade_construction, "capital")
        blueprint = self._get(trade_construction, "blueprint")

        construction_section = DashboardSectionProfile(
            section_id="TRADE_CONSTRUCTION",
            title="Trade Construction",
            status=self._status(
                allowed=construction_allowed,
                warnings=construction_warnings,
                rejections=construction_rejections,
            ),
            score=round(construction_score, 6),
            grade=construction_grade,
            metrics=(
                DashboardMetricProfile(
                    key="ticket_status",
                    label="Ticket Status",
                    value=str(
                        self._get(ticket, "ticket_status", "UNKNOWN")
                    ),
                    status=(
                        "PASS"
                        if self._get(ticket, "executable", False)
                        else "FAIL"
                    ),
                    severity=(
                        "NONE"
                        if self._get(ticket, "executable", False)
                        else "HIGH"
                    ),
                    description="Final executable trade-ticket state.",
                ),
                DashboardMetricProfile(
                    key="defined_risk",
                    label="Defined Risk",
                    value=str(
                        self._get(blueprint, "defined_risk", False)
                    ),
                    status=(
                        "PASS"
                        if self._get(blueprint, "defined_risk", False)
                        else "FAIL"
                    ),
                    severity=(
                        "NONE"
                        if self._get(blueprint, "defined_risk", False)
                        else "HIGH"
                    ),
                    description="Whether maximum loss is bounded.",
                ),
                DashboardMetricProfile(
                    key="reward_risk_ratio",
                    label="Reward/Risk",
                    value=f"{float(self._get(blueprint, 'reward_risk_ratio', 0.0)):.2f}",
                    status="INFO",
                    severity="NONE",
                    description="Maximum reward divided by maximum risk.",
                ),
                DashboardMetricProfile(
                    key="position_risk_pct",
                    label="Position Risk",
                    value=f"{float(self._get(capital, 'position_risk_pct', 0.0)):.2%}",
                    status="INFO",
                    severity="NONE",
                    description="Position risk as a percentage of equity.",
                ),
            ),
            warnings=construction_warnings,
            rejection_reasons=construction_rejections,
        )

        health = self._get(portfolio_allocation, "health")
        exposure = self._get(portfolio_allocation, "exposure")
        portfolio_score = float(
            self._get(health, "portfolio_health_score", 0.0)
        )
        portfolio_grade = str(
            self._get(
                health,
                "portfolio_health_grade",
                self._grade(portfolio_score),
            )
        )
        portfolio_allowed = bool(
            self._get(portfolio_allocation, "allowed", False)
        )
        portfolio_warnings = tuple(
            self._get(portfolio_allocation, "warnings", ()) or ()
        )
        portfolio_rejections = tuple(
            self._get(
                portfolio_allocation, "rejection_reasons", ()
            ) or ()
        )

        portfolio_section = DashboardSectionProfile(
            section_id="PORTFOLIO_ALLOCATION",
            title="Position Sizing and Portfolio Allocation",
            status=self._status(
                allowed=portfolio_allowed,
                warnings=portfolio_warnings,
                rejections=portfolio_rejections,
            ),
            score=round(portfolio_score, 6),
            grade=portfolio_grade,
            metrics=(
                DashboardMetricProfile(
                    key="positions_allocated",
                    label="Positions Allocated",
                    value=str(
                        self._get(
                            portfolio_allocation,
                            "positions_allocated",
                            0,
                        )
                    ),
                    status="INFO",
                    severity="NONE",
                    description="Number of approved portfolio positions.",
                ),
                DashboardMetricProfile(
                    key="portfolio_risk_pct",
                    label="Portfolio Risk",
                    value=f"{float(self._get(health, 'portfolio_risk_pct', 0.0)):.2%}",
                    status="INFO",
                    severity=str(
                        self._get(health, "risk_severity", "NONE")
                    ),
                    description="Total portfolio risk as percentage of equity.",
                ),
                DashboardMetricProfile(
                    key="capital_utilization_pct",
                    label="Capital Utilization",
                    value=f"{float(self._get(health, 'capital_utilization_pct', 0.0)):.2%}",
                    status="INFO",
                    severity="NONE",
                    description="Buying power consumed by proposed positions.",
                ),
                DashboardMetricProfile(
                    key="portfolio_delta",
                    label="Portfolio Delta",
                    value=f"{float(self._get(exposure, 'portfolio_delta', 0.0)):.2f}",
                    status="INFO",
                    severity="NONE",
                    description="Aggregate directional exposure.",
                ),
            ),
            warnings=portfolio_warnings,
            rejection_reasons=portfolio_rejections,
        )

        lifecycle_score = float(
            self._get(lifecycle, "lifecycle_score", 0.0)
        )
        lifecycle_grade = str(
            self._get(
                lifecycle,
                "lifecycle_grade",
                self._grade(lifecycle_score),
            )
        )
        lifecycle_allowed = bool(
            self._get(lifecycle, "allowed", False)
        )
        lifecycle_warnings = tuple(
            self._get(lifecycle, "warnings", ()) or ()
        )
        lifecycle_rejections = tuple(
            self._get(lifecycle, "rejection_reasons", ()) or ()
        )
        entry = self._get(lifecycle, "entry")
        exit_plan = self._get(lifecycle, "exit")

        lifecycle_section = DashboardSectionProfile(
            section_id="TRADE_LIFECYCLE",
            title="Trade Lifecycle",
            status=self._status(
                allowed=lifecycle_allowed,
                warnings=lifecycle_warnings,
                rejections=lifecycle_rejections,
            ),
            score=round(lifecycle_score, 6),
            grade=lifecycle_grade,
            metrics=(
                DashboardMetricProfile(
                    key="entry_status",
                    label="Entry Status",
                    value=str(
                        self._get(entry, "entry_status", "UNKNOWN")
                    ),
                    status=(
                        "PASS"
                        if self._get(entry, "entry_allowed", False)
                        else "FAIL"
                    ),
                    severity=(
                        "NONE"
                        if self._get(entry, "entry_allowed", False)
                        else "HIGH"
                    ),
                    description="Lifecycle entry readiness.",
                ),
                DashboardMetricProfile(
                    key="days_to_expiration",
                    label="Days to Expiration",
                    value=str(
                        self._get(entry, "days_to_expiration", 0)
                    ),
                    status="INFO",
                    severity="NONE",
                    description="Remaining duration at planned entry.",
                ),
                DashboardMetricProfile(
                    key="profit_target",
                    label="Profit Target",
                    value=f"{float(self._get(exit_plan, 'profit_target_value', 0.0)):.2f}",
                    status="INFO",
                    severity="NONE",
                    description="Planned profit-taking threshold.",
                ),
                DashboardMetricProfile(
                    key="stop_loss",
                    label="Stop Loss",
                    value=f"{float(self._get(exit_plan, 'stop_loss_value', 0.0)):.2f}",
                    status="INFO",
                    severity="NONE",
                    description="Planned loss-control threshold.",
                ),
            ),
            warnings=lifecycle_warnings,
            rejection_reasons=lifecycle_rejections,
        )

        governance_score = float(
            self._get(governance, "governance_score", 0.0)
        )
        governance_grade = str(
            self._get(
                governance,
                "governance_grade",
                self._grade(governance_score),
            )
        )
        governance_allowed = bool(
            self._get(governance, "allowed", False)
        )
        governance_warnings = tuple(
            self._get(governance, "warnings", ()) or ()
        )
        governance_rejections = tuple(
            self._get(governance, "rejection_reasons", ()) or ()
        )
        approval_status = str(
            self._get(governance, "approval_status", "UNKNOWN")
        )

        governance_section = DashboardSectionProfile(
            section_id="PRETRADE_GOVERNANCE",
            title="Pre-Trade Governance",
            status=self._status(
                allowed=governance_allowed,
                warnings=governance_warnings,
                rejections=governance_rejections,
            ),
            score=round(governance_score, 6),
            grade=governance_grade,
            metrics=(
                DashboardMetricProfile(
                    key="approval_status",
                    label="Approval Status",
                    value=approval_status,
                    status=(
                        "PASS"
                        if governance_allowed
                        else "FAIL"
                    ),
                    severity=str(
                        self._get(
                            governance,
                            "risk_severity",
                            "UNKNOWN",
                        )
                    ),
                    description="Final institutional approval state.",
                ),
                DashboardMetricProfile(
                    key="confidence_score",
                    label="Confidence Score",
                    value=f"{float(self._get(governance, 'confidence_score', 0.0)):.2f}",
                    status="INFO",
                    severity="NONE",
                    description="Integrated confidence across Phase 3.",
                ),
                DashboardMetricProfile(
                    key="rule_count",
                    label="Rules Evaluated",
                    value=str(
                        len(
                            tuple(
                                self._get(
                                    governance,
                                    "rules",
                                    (),
                                ) or ()
                            )
                        )
                    ),
                    status="INFO",
                    severity="NONE",
                    description="Number of governance rules evaluated.",
                ),
                DashboardMetricProfile(
                    key="audit_count",
                    label="Audit Records",
                    value=str(
                        len(
                            tuple(
                                self._get(
                                    governance,
                                    "audit_trail",
                                    (),
                                ) or ()
                            )
                        )
                    ),
                    status="INFO",
                    severity="NONE",
                    description="Immutable governance audit records.",
                ),
            ),
            warnings=governance_warnings,
            rejection_reasons=governance_rejections,
        )

        sections = (
            construction_section,
            portfolio_section,
            lifecycle_section,
            governance_section,
        )
        overall_score = round(
            sum(section.score for section in sections)
            / len(sections),
            6,
        )

        all_warnings = tuple(
            dict.fromkeys(
                warning
                for section in sections
                for warning in section.warnings
            )
        )
        all_rejections = tuple(
            dict.fromkeys(
                reason
                for section in sections
                for reason in section.rejection_reasons
            )
        )
        remediation = tuple(
            self._get(governance, "remediation_actions", ()) or ()
        )

        execution_allowed = (
            construction_allowed
            and portfolio_allowed
            and lifecycle_allowed
            and governance_allowed
        )

        if all_rejections:
            overall_status = "BLOCKED"
        elif execution_allowed and all_warnings:
            overall_status = "READY_WITH_WARNINGS"
        elif execution_allowed:
            overall_status = "READY"
        else:
            overall_status = "REVIEW_REQUIRED"

        return Phase3DashboardProfile(
            trade_id=trade_id,
            symbol=symbol,
            strategy_name=strategy_name,
            overall_status=overall_status,
            overall_score=overall_score,
            overall_grade=self._grade(overall_score),
            risk_severity=str(
                self._get(governance, "risk_severity", "UNKNOWN")
            ),
            execution_allowed=execution_allowed,
            sections=sections,
            approval_status=approval_status,
            approval_recommendation=str(
                self._get(
                    governance,
                    "approval_recommendation",
                    "No recommendation available.",
                )
            ),
            warnings=all_warnings,
            rejection_reasons=all_rejections,
            remediation_actions=remediation,
            metadata={
                "milestone": 34,
                "phase": 3,
                "step": 5,
                "source": "PHASE3_DASHBOARD_REPORTING",
                "phase_status": "COMPLETE",
            },
        )
