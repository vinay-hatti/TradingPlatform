from trading_ai.strategy_engine.walk_forward_integration_policy import WalkForwardIntegrationPolicy
from trading_ai.strategy_engine.walk_forward_integration_profile import WalkForwardIntegrationProfile


class WalkForwardIntegrationService:
    def __init__(self, policy=None):
        self.policy = policy or WalkForwardIntegrationPolicy()
        self.policy.validate()

    @staticmethod
    def _value(profile, name, default=None):
        if profile is None:
            return default
        if isinstance(profile, dict):
            return profile.get(name, default)
        return getattr(profile, name, default)

    def evaluate(self, profile, source="INSTITUTIONAL_WALK_FORWARD"):
        if not self.policy.enabled:
            return WalkForwardIntegrationProfile(
                valid=False,
                allowed=True,
                source="DISABLED",
                warnings=["WALK_FORWARD_INTEGRATION_DISABLED"],
            )
        if profile is None:
            return WalkForwardIntegrationProfile(
                valid=False,
                allowed=not self.policy.require_valid_profile,
                source="UNAVAILABLE",
                warnings=["WALK_FORWARD_PROFILE_UNAVAILABLE"],
                rejection_reasons=(
                    ["WALK_FORWARD_PROFILE_REQUIRED"]
                    if self.policy.require_valid_profile else []
                ),
            )

        valid = bool(self._value(profile, "valid", False))
        source_allowed = bool(self._value(profile, "allowed", True))
        score = float(self._value(profile, "walk_forward_score", 0.0) or 0.0)
        stability = float(self._value(profile, "parameter_stability_score", 0.0) or 0.0)
        degradation = float(self._value(profile, "average_degradation_pct", 0.0) or 0.0)
        severity = str(self._value(profile, "risk_severity", "UNKNOWN") or "UNKNOWN").upper()
        warnings = list(self._value(profile, "warnings", []) or [])
        rejections = list(self._value(profile, "rejection_reasons", []) or [])

        if not valid and self.policy.require_valid_profile:
            rejections.append("WALK_FORWARD_PROFILE_INVALID")
        if score < self.policy.minimum_walk_forward_score:
            warnings.append("WALK_FORWARD_SCORE_BELOW_THRESHOLD")
        if stability < self.policy.minimum_parameter_stability_score:
            warnings.append("WALK_FORWARD_PARAMETER_STABILITY_LOW")
        if degradation > self.policy.maximum_degradation_pct:
            warnings.append("WALK_FORWARD_DEGRADATION_HIGH")
        if self.policy.reject_critical_severity and severity == "CRITICAL":
            rejections.append("WALK_FORWARD_CRITICAL_RISK")
        if self.policy.reject_unapproved_profile and not source_allowed:
            rejections.append("WALK_FORWARD_PROFILE_NOT_APPROVED")

        allowed = not rejections
        return WalkForwardIntegrationProfile(
            valid=valid,
            allowed=allowed,
            source=source,
            window_count=int(self._value(profile, "window_count", 0) or 0),
            completed_window_count=int(self._value(profile, "completed_window_count", 0) or 0),
            aggregate_oos_return=float(self._value(profile, "aggregate_oos_return", 0.0) or 0.0),
            average_oos_sharpe=float(self._value(profile, "average_oos_sharpe", 0.0) or 0.0),
            worst_oos_drawdown_pct=float(self._value(profile, "worst_oos_drawdown_pct", 0.0) or 0.0),
            average_degradation_pct=degradation,
            parameter_stability_score=stability,
            window_consistency_score=float(self._value(profile, "window_consistency_score", 0.0) or 0.0),
            walk_forward_score=score,
            walk_forward_grade=str(self._value(profile, "walk_forward_grade", "N/A") or "N/A").upper(),
            risk_severity=severity,
            raw_profile=profile,
            warnings=list(dict.fromkeys(warnings)),
            rejection_reasons=list(dict.fromkeys(rejections)),
            metadata={"source_allowed": source_allowed},
        )

    def attach(self, decisions, profile):
        for decision in decisions or []:
            decision.walk_forward_validated = bool(profile.valid)
            decision.walk_forward_allowed = bool(profile.allowed)
            decision.walk_forward_score = float(profile.walk_forward_score)
            decision.walk_forward_grade = str(profile.walk_forward_grade)
            decision.walk_forward_severity = str(profile.risk_severity)
            decision.walk_forward_oos_return = float(profile.aggregate_oos_return)
            decision.walk_forward_oos_sharpe = float(profile.average_oos_sharpe)
            decision.walk_forward_worst_drawdown_pct = float(profile.worst_oos_drawdown_pct)
            decision.walk_forward_parameter_stability = float(profile.parameter_stability_score)
            decision.walk_forward_profile = profile
            decision.metadata["walk_forward_profile"] = profile
            decision.warnings.extend(x for x in profile.warnings if x not in decision.warnings)
            if not profile.allowed:
                decision.allowed = False
                decision.rejection_reasons.extend(
                    x for x in profile.rejection_reasons
                    if x not in decision.rejection_reasons
                )
        return decisions
