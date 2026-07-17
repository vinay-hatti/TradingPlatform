from __future__ import annotations

from dataclasses import replace
from typing import Any

from .environment_profile import EnvironmentProfile, EnvironmentPromotionProfile
from .environment_registry_policy import EnvironmentRegistryPolicy


class EnvironmentPromotionEngine:
    def __init__(self, policy: EnvironmentRegistryPolicy | None = None) -> None:
        self.policy = policy or EnvironmentRegistryPolicy()
        self.policy.validate()

    def evaluate(
        self,
        source: EnvironmentProfile,
        target_environment: str,
        *,
        target_runtime_score: float | None = None,
        target_runtime_allowed: bool | None = None,
        manual_approval: bool = False,
    ) -> EnvironmentPromotionProfile:
        target = target_environment.lower()
        reasons: list[str] = []
        warnings: list[str] = []
        path_allowed = (source.name, target) in self.policy.allowed_promotion_paths
        if not path_allowed:
            reasons.append("PROMOTION_PATH_NOT_ALLOWED")
        if self.policy.require_source_allowed and not source.runtime_allowed:
            reasons.append("SOURCE_RUNTIME_NOT_ALLOWED")
        if source.runtime_score < self.policy.minimum_source_runtime_score:
            reasons.append("SOURCE_RUNTIME_SCORE_BELOW_MINIMUM")
        if self.policy.require_target_validation:
            if target_runtime_score is None or target_runtime_allowed is None:
                reasons.append("TARGET_RUNTIME_VALIDATION_REQUIRED")
            else:
                if target_runtime_score < self.policy.minimum_target_runtime_score:
                    reasons.append("TARGET_RUNTIME_SCORE_BELOW_MINIMUM")
                if not target_runtime_allowed:
                    reasons.append("TARGET_RUNTIME_NOT_ALLOWED")
        if target == "production" and self.policy.require_manual_production_promotion and not manual_approval:
            reasons.append("MANUAL_PRODUCTION_APPROVAL_REQUIRED")

        config = source.configuration
        debug = bool(config.get("debug", False))
        trading = config.get("trading", {}) if isinstance(config.get("trading", {}), dict) else {}
        if target == "production" and self.policy.block_debug_in_production and debug:
            reasons.append("DEBUG_ENABLED_FOR_PRODUCTION")
        if target != "production" and self.policy.block_live_trading_before_production and bool(trading.get("live_enabled", False)):
            reasons.append("LIVE_TRADING_BEFORE_PRODUCTION")
        if target == "production" and self.policy.require_kill_switch_for_production and not bool(trading.get("kill_switch_enabled", False)):
            reasons.append("PRODUCTION_KILL_SWITCH_REQUIRED")

        source_component = min(max(source.runtime_score, 0.0), 100.0)
        target_component = min(max(target_runtime_score or 0.0, 0.0), 100.0)
        score = round(source_component * 0.45 + target_component * 0.55, 2)
        allowed = not reasons
        if score >= 95:
            grade, severity = "A", "LOW"
        elif score >= 90:
            grade, severity = "B", "MODERATE"
        elif score >= 75:
            grade, severity = "C", "SEVERE"
        else:
            grade, severity = "F", "CRITICAL"

        return EnvironmentPromotionProfile(
            valid=True,
            allowed=allowed,
            source_environment=source.name,
            target_environment=target,
            source_version=source.version,
            target_version=None,
            promotion_score=score,
            grade=grade,
            severity=severity,
            recommendation="PROMOTE" if allowed else "REJECT_PROMOTION",
            warnings=tuple(warnings),
            rejection_reasons=tuple(reasons),
            metadata={"source_hash": source.configuration_hash},
        )
