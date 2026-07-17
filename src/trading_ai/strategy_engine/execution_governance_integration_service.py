from __future__ import annotations

from typing import Any, Iterable, Sequence

from .execution_governance_integration_policy import ExecutionGovernanceIntegrationPolicy
from .execution_governance_integration_profile import ExecutionGovernanceIntegrationProfile
from .execution_governance_service import ExecutionGovernanceService


class ExecutionGovernanceIntegrationService:
    """Integrate Step 5 governance outcomes into institutional decisions."""

    def __init__(self, policy=None, governance_service=None):
        self.policy = policy or ExecutionGovernanceIntegrationPolicy()
        self.policy.validate()
        self.governance_service = governance_service or ExecutionGovernanceService()

    @staticmethod
    def _value(obj: Any, name: str, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    def analyze(
        self,
        *,
        baseline_observations: Sequence[Any] | Iterable[Any] | None = None,
        current_observations: Sequence[Any] | Iterable[Any] | None = None,
        governance_profile: Any = None,
        route_registry_profile: Any = None,
        champion_challenger_profile: Any = None,
        baseline_name: str = "BASELINE",
        current_name: str = "CURRENT",
    ) -> ExecutionGovernanceIntegrationProfile:
        if not self.policy.enabled:
            return ExecutionGovernanceIntegrationProfile(valid=False, allowed=True, warnings=("EXECUTION_GOVERNANCE_INTEGRATION_DISABLED",))

        warnings = []
        rejections = []
        if governance_profile is None and (baseline_observations is not None or current_observations is not None):
            governance_profile = self.governance_service.analyze(
                list(baseline_observations or []), list(current_observations or []),
                baseline_name=baseline_name, current_name=current_name,
            )

        gov_available = bool(self._value(governance_profile, "valid", False))
        gov_allowed = bool(self._value(governance_profile, "allowed", True))
        score = float(self._value(governance_profile, "governance_score", 0.0) or 0.0)
        severity = str(self._value(governance_profile, "drift_severity", "UNKNOWN") or "UNKNOWN").upper()

        if not gov_available:
            warnings.append("EXECUTION_GOVERNANCE_PROFILE_UNAVAILABLE")
            if self.policy.require_valid_governance_profile:
                rejections.append("VALID_EXECUTION_GOVERNANCE_PROFILE_REQUIRED")
        else:
            warnings.extend(self._value(governance_profile, "warnings", ()) or ())
            if score < self.policy.minimum_governance_score:
                warnings.append("EXECUTION_GOVERNANCE_SCORE_BELOW_INTEGRATION_MINIMUM")
                if self.policy.reject_unapproved_governance:
                    rejections.append("EXECUTION_GOVERNANCE_SCORE_BELOW_INTEGRATION_MINIMUM")
            if not gov_allowed and self.policy.reject_unapproved_governance:
                rejections.extend(self._value(governance_profile, "rejection_reasons", ()) or ("EXECUTION_GOVERNANCE_NOT_ALLOWED",))
            if severity in {"SEVERE", "CRITICAL"} and self.policy.reject_severe_governance:
                rejections.append("SEVERE_EXECUTION_DRIFT")

        registry_available = bool(self._value(route_registry_profile, "valid", False))
        route_count = int(self._value(route_registry_profile, "route_count", 0) or 0)
        champion_version = str(self._value(route_registry_profile, "champion_version", "UNAVAILABLE") or "UNAVAILABLE")
        if not registry_available:
            warnings.append("EXECUTION_ROUTE_REGISTRY_UNAVAILABLE")
            if self.policy.require_route_registry:
                rejections.append("EXECUTION_ROUTE_REGISTRY_REQUIRED")
        elif self.policy.require_champion_route and champion_version == "UNAVAILABLE":
            rejections.append("EXECUTION_CHAMPION_ROUTE_REQUIRED")

        cc_available = bool(self._value(champion_challenger_profile, "valid", False))
        if not cc_available and not self.policy.allow_missing_champion_challenger:
            rejections.append("CHAMPION_CHALLENGER_EVALUATION_REQUIRED")
        elif cc_available:
            warnings.extend(self._value(champion_challenger_profile, "warnings", ()) or ())

        allowed = not rejections
        valid = gov_available or registry_available or cc_available
        return ExecutionGovernanceIntegrationProfile(
            valid=valid, allowed=allowed, governance_available=gov_available,
            governance_score=score, governance_grade=str(self._value(governance_profile, "governance_grade", "N/A")),
            governance_severity=severity, aggregate_psi=float(self._value(governance_profile, "aggregate_psi", 0.0) or 0.0),
            maximum_metric_psi=float(self._value(governance_profile, "maximum_metric_psi", 0.0) or 0.0),
            deteriorated_metric_count=int(self._value(governance_profile, "deteriorated_metric_count", 0) or 0),
            governance_recommendation=str(self._value(governance_profile, "recommendation", "UNAVAILABLE")),
            route_registry_available=registry_available, route_count=route_count,
            active_route_version=str(self._value(route_registry_profile, "active_version", "UNAVAILABLE")),
            champion_route_version=champion_version,
            challenger_route_versions=tuple(self._value(route_registry_profile, "challenger_versions", ()) or ()),
            champion_challenger_available=cc_available,
            challenger_version=str(self._value(champion_challenger_profile, "challenger_version", "UNAVAILABLE")),
            challenger_evaluation_score=float(self._value(champion_challenger_profile, "evaluation_score", 0.0) or 0.0),
            challenger_recommendation=str(self._value(champion_challenger_profile, "recommendation", "UNAVAILABLE")),
            route_promotion_recommended=bool(cc_available and self._value(champion_challenger_profile, "allowed", False) and str(self._value(champion_challenger_profile, "recommendation", "")).upper() in {"PROMOTE_CHALLENGER", "PROMOTE"}),
            execution_governance_profile=governance_profile,
            execution_route_registry_profile=route_registry_profile,
            execution_champion_challenger_profile=champion_challenger_profile,
            warnings=tuple(dict.fromkeys(map(str, warnings))),
            rejection_reasons=tuple(dict.fromkeys(map(str, rejections))),
            metadata={"source": "PHASE9_STEP5_EXECUTION_GOVERNANCE_INTEGRATION"},
        )

    evaluate = analyze

    def attach(self, decisions, profile):
        for decision in decisions or []:
            decision.execution_governance_valid = profile.valid
            decision.execution_governance_allowed = profile.allowed
            decision.execution_governance_score = round(profile.governance_score, 4)
            decision.execution_governance_grade = profile.governance_grade
            decision.execution_governance_severity = profile.governance_severity
            decision.execution_governance_aggregate_psi = round(profile.aggregate_psi, 6)
            decision.execution_governance_recommendation = profile.governance_recommendation
            decision.execution_route_registry_available = profile.route_registry_available
            decision.execution_active_route_version = profile.active_route_version
            decision.execution_champion_route_version = profile.champion_route_version
            decision.execution_challenger_route_version = profile.challenger_version
            decision.execution_route_promotion_recommended = profile.route_promotion_recommended
            decision.execution_governance_integration_profile = profile
            if not isinstance(getattr(decision, "metadata", None), dict):
                decision.metadata = {}
            decision.metadata["execution_governance_integration_profile"] = profile
            decision.warnings.extend(x for x in profile.warnings if x not in decision.warnings)
            if not profile.allowed:
                decision.rejection_reasons.extend(x for x in profile.rejection_reasons if x not in decision.rejection_reasons)
                decision.allowed = False
        return decisions
