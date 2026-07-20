from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class GovernanceRuleResultProfile:
    rule_id: str
    rule_group: str
    name: str
    passed: bool
    severity: str
    actual_value: str
    threshold_value: str
    message: str
    remediation: str
    blocking: bool


@dataclass(frozen=True)
class GovernanceAuditRecordProfile:
    timestamp: datetime
    rule_id: str
    outcome: str
    actual_value: str
    threshold_value: str
    source_component: str
    reviewer: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class GovernanceOverrideProfile:
    requested: bool
    approved: bool
    reviewer: str | None
    reason: str | None
    scope: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApprovalChainEntryProfile:
    level: str
    required: bool
    status: str
    reviewer_role: str
    rationale: str


@dataclass(frozen=True)
class GovernanceDecisionProfile:
    trade_id: str
    symbol: str
    strategy_name: str
    governance_score: float
    governance_grade: str
    confidence_score: float
    risk_severity: str
    approval_status: str
    approval_recommendation: str
    allowed: bool
    rules: tuple[GovernanceRuleResultProfile, ...]
    audit_trail: tuple[GovernanceAuditRecordProfile, ...]
    approval_chain: tuple[ApprovalChainEntryProfile, ...]
    override: GovernanceOverrideProfile
    positive_factors: tuple[str, ...] = ()
    residual_risks: tuple[str, ...] = ()
    remediation_actions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
