from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .secret_governance_policy import SecretGovernancePolicy
from .secret_governance_profile import (
    CredentialHealthCheckProfile,
    CredentialHealthProfile,
    SecretGovernanceProfile,
    SecretInventoryEntryProfile,
    SecretRotationProfile,
)
from .secret_provider import CompositeSecretProvider, SecretProvider


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def secret_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class CredentialHealthEngine:
    def __init__(self, policy: SecretGovernancePolicy | None = None) -> None:
        self.policy = policy or SecretGovernancePolicy()
        self.policy.validate()

    def _resolve(
        self,
        provider: SecretProvider | None,
        name: str,
    ) -> tuple[str | None, str]:
        if provider is None:
            return None, "unavailable"
        if isinstance(provider, CompositeSecretProvider):
            return provider.resolve(name)
        value = provider.get(name)
        return value, provider.name if value is not None else "unavailable"

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95.0:
            return "A", "LOW"
        if score >= 85.0:
            return "B", "MODERATE"
        if score >= 70.0:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate_credential(
        self,
        entry: SecretInventoryEntryProfile,
        provider: SecretProvider | None,
        *,
        now: datetime | None = None,
    ) -> CredentialHealthProfile:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        value, provider_name = self._resolve(provider, entry.name)
        resolved = value is not None

        base_time = _parse_datetime(entry.rotated_at) or _parse_datetime(entry.created_at)
        expiry = _parse_datetime(entry.expires_at)
        age_days = (
            (now - base_time).total_seconds() / 86400.0
            if base_time is not None else None
        )
        days_until_expiry = (
            (expiry - now).total_seconds() / 86400.0
            if expiry is not None else None
        )

        checks: list[CredentialHealthCheckProfile] = []

        def add(
            name: str,
            passed: bool,
            message: str,
            *,
            required: bool = True,
            severity: str = "CRITICAL",
            metadata: dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                CredentialHealthCheckProfile(
                    name=name,
                    passed=passed,
                    required=required,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else severity,
                    message=message,
                    metadata=metadata or {},
                )
            )

        add(
            "enabled",
            entry.enabled,
            "Credential inventory entry is enabled.",
        )
        add(
            "owner",
            bool(entry.owner) or not self.policy.require_rotation_owner,
            "Credential has an accountable rotation owner.",
        )
        add(
            "provider_resolution",
            resolved or not self.policy.require_provider_resolution,
            "Credential resolves through an approved secret provider.",
            metadata={"provider": provider_name},
        )
        add(
            "minimum_length",
            value is None or len(value) >= self.policy.minimum_secret_length,
            "Credential meets the minimum length policy.",
            severity="SEVERE",
        )

        overdue = age_days is not None and age_days > self.policy.maximum_age_days
        add(
            "rotation_age",
            not overdue or not self.policy.reject_overdue_rotation,
            "Credential rotation age is within policy.",
            metadata={"age_days": age_days},
        )

        expired = days_until_expiry is not None and days_until_expiry < 0
        add(
            "expiry",
            not expired or not self.policy.reject_expired_secrets,
            "Credential is not expired.",
            metadata={"days_until_expiry": days_until_expiry},
        )

        fingerprint_matches = (
            value is None
            or entry.fingerprint is None
            or secret_fingerprint(value) == entry.fingerprint
        )
        add(
            "fingerprint",
            fingerprint_matches,
            "Resolved credential matches the registered fingerprint.",
            severity="CRITICAL",
        )

        required = [item for item in checks if item.required]
        failed = [item for item in required if not item.passed]
        score = (
            sum(item.score for item in required) / len(required)
            if required else 100.0
        )

        warnings: list[str] = []
        if age_days is not None and self.policy.warning_age_days <= age_days <= self.policy.maximum_age_days:
            warnings.append("SECRET_ROTATION_APPROACHING")
        if (
            days_until_expiry is not None
            and 0 <= days_until_expiry <= self.policy.expiry_warning_days
        ):
            warnings.append("SECRET_EXPIRY_APPROACHING")

        grade, severity = self._grade(score)
        allowed = not failed and score >= self.policy.minimum_health_score
        rotation_required = overdue or expired
        rejection_reasons = tuple(item.name.upper() for item in failed)

        return CredentialHealthProfile(
            name=entry.name,
            environment=entry.environment,
            valid=True,
            allowed=allowed,
            resolved=resolved,
            provider=provider_name,
            age_days=round(age_days, 4) if age_days is not None else None,
            days_until_expiry=(
                round(days_until_expiry, 4)
                if days_until_expiry is not None else None
            ),
            score=round(score, 2),
            grade=grade,
            severity=severity,
            rotation_required=rotation_required,
            recommendation=(
                "USE"
                if allowed and not warnings
                else "ROTATE_SOON"
                if allowed
                else "BLOCK_CREDENTIAL"
            ),
            checks=tuple(checks),
            warnings=tuple(warnings),
            rejection_reasons=rejection_reasons,
            metadata={
                "registered_provider": entry.provider,
                "version": entry.version,
                "required": entry.required,
            },
        )

    def evaluate_environment(
        self,
        environment: str,
        entries: tuple[SecretInventoryEntryProfile, ...] | list[SecretInventoryEntryProfile],
        provider: SecretProvider | None,
        *,
        now: datetime | None = None,
    ) -> SecretGovernanceProfile:
        credentials = tuple(
            self.evaluate_credential(entry, provider, now=now)
            for entry in entries
            if entry.environment.strip().lower() == environment.strip().lower()
        )
        if not credentials:
            return SecretGovernanceProfile(
                valid=False,
                allowed=False,
                environment=environment,
                secret_count=0,
                healthy_count=0,
                warning_count=0,
                rejected_count=0,
                score=0.0,
                grade="F",
                severity="CRITICAL",
                recommendation="BLOCK_STARTUP",
                rejection_reasons=("NO_SECRET_INVENTORY",),
            )

        healthy = sum(item.allowed for item in credentials)
        warning_count = sum(bool(item.warnings) for item in credentials)
        rejected = len(credentials) - healthy
        score = sum(item.score for item in credentials) / len(credentials)
        grade, severity = self._grade(score)

        production = environment.strip().lower() == self.policy.production_environment
        allowed = rejected == 0 and score >= self.policy.minimum_health_score
        if production and self.policy.fail_closed_in_production:
            allowed = allowed and all(
                item.allowed for item in credentials if item.metadata.get("required", True)
            )

        warnings = tuple(
            f"{item.name}:{warning}"
            for item in credentials
            for warning in item.warnings
        )
        rejection_reasons = tuple(
            f"{item.name}:{reason}"
            for item in credentials
            for reason in item.rejection_reasons
        )

        return SecretGovernanceProfile(
            valid=True,
            allowed=allowed,
            environment=environment,
            secret_count=len(credentials),
            healthy_count=healthy,
            warning_count=warning_count,
            rejected_count=rejected,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="START" if allowed else "BLOCK_STARTUP",
            credentials=credentials,
            warnings=warnings,
            rejection_reasons=rejection_reasons,
            metadata={
                "production_fail_closed": (
                    production and self.policy.fail_closed_in_production
                )
            },
        )

    def evaluate_rotation(
        self,
        entry: SecretInventoryEntryProfile,
        new_value: str,
        *,
        new_version: str,
        actor: str,
        reason: str,
        manual_approval: bool = False,
    ) -> SecretRotationProfile:
        new_fingerprint = secret_fingerprint(new_value)
        reasons: list[str] = []
        warnings: list[str] = []

        if len(new_value) < self.policy.minimum_secret_length:
            reasons.append("SECRET_TOO_SHORT")
        if (
            self.policy.reject_reused_fingerprint
            and entry.fingerprint
            and new_fingerprint == entry.fingerprint
        ):
            reasons.append("SECRET_REUSE_DETECTED")
        if self.policy.require_rotation_owner and not actor.strip():
            reasons.append("ROTATION_ACTOR_REQUIRED")
        if not reason.strip():
            reasons.append("ROTATION_REASON_REQUIRED")

        production = entry.environment == self.policy.production_environment
        if (
            production
            and self.policy.require_manual_production_rotation_approval
            and not manual_approval
        ):
            reasons.append("MANUAL_PRODUCTION_ROTATION_APPROVAL_REQUIRED")

        score = max(0.0, 100.0 - 25.0 * len(reasons))
        grade, severity = self._grade(score)
        allowed = not reasons and score >= self.policy.minimum_health_score

        return SecretRotationProfile(
            valid=True,
            allowed=allowed,
            name=entry.name,
            environment=entry.environment,
            previous_version=entry.version,
            new_version=str(new_version),
            previous_fingerprint=entry.fingerprint,
            new_fingerprint=new_fingerprint,
            actor=actor,
            reason=reason,
            promotion_score=score,
            grade=grade,
            severity=severity,
            recommendation="ROTATE" if allowed else "REJECT_ROTATION",
            warnings=tuple(warnings),
            rejection_reasons=tuple(reasons),
        )
