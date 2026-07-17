from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from .startup_readiness_policy import StartupReadinessPolicy
from .startup_readiness_profile import (
    StartupGateCheckProfile,
    StartupReadinessProfile,
)


class StartupReadinessEngine:
    def __init__(self, policy: StartupReadinessPolicy | None = None) -> None:
        self.policy = policy or StartupReadinessPolicy()
        self.policy.validate()

    @staticmethod
    def _value(obj: Any, name: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    @staticmethod
    def _json_dict(obj: Any) -> dict[str, Any] | None:
        if obj is None:
            return None
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, dict):
            return dict(obj)
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return {"repr": repr(obj)}

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 97.0:
            return "A+", "LOW"
        if score >= 92.0:
            return "A", "LOW"
        if score >= 85.0:
            return "B", "MODERATE"
        if score >= 70.0:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate(
        self,
        *,
        environment: str,
        configuration_fingerprint: str,
        runtime_profile: Any = None,
        environment_registry_profile: Any = None,
        secret_governance_profile: Any = None,
    ) -> StartupReadinessProfile:
        checks: list[StartupGateCheckProfile] = []

        def add(
            name: str,
            category: str,
            passed: bool,
            required: bool,
            score: float,
            message: str,
            severity: str = "CRITICAL",
            metadata: dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                StartupGateCheckProfile(
                    name=name,
                    category=category,
                    passed=bool(passed),
                    required=required,
                    score=max(0.0, min(100.0, float(score))),
                    severity="LOW" if passed else severity,
                    message=message,
                    metadata=metadata or {},
                )
            )

        runtime_available = runtime_profile is not None
        runtime_allowed = bool(self._value(runtime_profile, "allowed", False))
        runtime_score = float(self._value(runtime_profile, "score", 0.0) or 0.0)
        add(
            "runtime_safety",
            "runtime",
            runtime_available and runtime_allowed,
            self.policy.require_runtime_safety,
            runtime_score,
            "Runtime configuration and filesystem safety checks must pass.",
            metadata={"available": runtime_available},
        )

        registry_available = environment_registry_profile is not None
        registry_allowed = bool(
            self._value(environment_registry_profile, "allowed", False)
        )
        environment_score = float(
            self._value(
                environment_registry_profile,
                "runtime_score",
                self._value(environment_registry_profile, "score", 0.0),
            )
            or 0.0
        )
        active = bool(
            self._value(
                environment_registry_profile,
                "active",
                self._value(environment_registry_profile, "is_active", False),
            )
        )
        active_version = self._value(
            environment_registry_profile,
            "version",
            self._value(environment_registry_profile, "active_version", None),
        )
        registered_fingerprint = self._value(
            environment_registry_profile,
            "configuration_fingerprint",
            self._value(environment_registry_profile, "fingerprint", None),
        )

        add(
            "environment_registry",
            "environment",
            registry_available and registry_allowed,
            self.policy.require_environment_registry,
            environment_score,
            "Environment configuration must be registered and approved.",
            metadata={"available": registry_available},
        )
        add(
            "active_environment_version",
            "environment",
            active,
            self.policy.require_active_environment_version,
            100.0 if active else 0.0,
            "An active configuration version is required for this environment.",
            metadata={"active_version": active_version},
        )
        fingerprint_matches = bool(
            registered_fingerprint
            and configuration_fingerprint
            and registered_fingerprint == configuration_fingerprint
        )
        add(
            "configuration_fingerprint",
            "environment",
            fingerprint_matches,
            self.policy.require_configuration_fingerprint_match,
            100.0 if fingerprint_matches else 0.0,
            "Loaded configuration must match the active registered fingerprint.",
            metadata={
                "loaded": configuration_fingerprint,
                "registered": registered_fingerprint,
            },
        )

        secret_available = secret_governance_profile is not None
        secret_allowed = bool(
            self._value(secret_governance_profile, "allowed", False)
        )
        secret_score = float(
            self._value(secret_governance_profile, "score", 0.0) or 0.0
        )
        add(
            "secret_governance",
            "secrets",
            secret_available and secret_allowed,
            self.policy.require_secret_governance,
            secret_score,
            "All required credentials must pass health and rotation governance.",
            metadata={"available": secret_available},
        )

        runtime_weight, environment_weight, secret_weight = (
            self.policy.normalized_weights()
        )
        component_score = (
            runtime_score * runtime_weight
            + environment_score * environment_weight
            + secret_score * secret_weight
        )

        required_failed = [
            check for check in checks if check.required and not check.passed
        ]
        allowed = (
            not required_failed
            and component_score >= self.policy.minimum_readiness_score
        )
        if not self.policy.fail_closed:
            allowed = component_score >= self.policy.minimum_readiness_score

        grade, severity = self._grade(component_score)
        warnings = tuple(
            check.name.upper()
            for check in checks
            if not check.passed and not check.required
        )
        rejection_reasons = tuple(
            check.name.upper() for check in required_failed
        )

        return StartupReadinessProfile(
            valid=True,
            allowed=allowed,
            environment=environment,
            score=round(component_score, 2),
            grade=grade,
            severity=severity,
            recommendation="START" if allowed else "BLOCK_STARTUP",
            active_environment_version=str(active_version) if active_version else None,
            configuration_fingerprint=configuration_fingerprint,
            registered_configuration_fingerprint=registered_fingerprint,
            runtime_score=round(runtime_score, 2),
            environment_score=round(environment_score, 2),
            secret_score=round(secret_score, 2),
            checks=tuple(checks),
            warnings=warnings,
            rejection_reasons=rejection_reasons,
            runtime_profile=self._json_dict(runtime_profile),
            environment_profile=self._json_dict(environment_registry_profile),
            secret_profile=self._json_dict(secret_governance_profile),
            metadata={
                "minimum_readiness_score": self.policy.minimum_readiness_score,
                "weights": {
                    "runtime": runtime_weight,
                    "environment": environment_weight,
                    "secrets": secret_weight,
                },
                "required_failure_count": len(required_failed),
            },
        )
