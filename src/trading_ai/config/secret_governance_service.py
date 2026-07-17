from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .credential_health_engine import CredentialHealthEngine
from .secret_governance_policy import SecretGovernancePolicy
from .secret_governance_profile import (
    SecretGovernanceProfile,
    SecretInventoryEntryProfile,
    SecretRotationProfile,
)
from .secret_inventory_registry import SecretInventoryRegistry
from .secret_provider import EnvironmentSecretProvider, SecretProvider


class SecretGovernanceService:
    def __init__(
        self,
        registry_path: str | Path = "config/secret_inventory.json",
        *,
        policy: SecretGovernancePolicy | None = None,
        provider: SecretProvider | None = None,
    ) -> None:
        self.policy = policy or SecretGovernancePolicy()
        self.engine = CredentialHealthEngine(self.policy)
        self.provider = provider or EnvironmentSecretProvider()
        self.registry = SecretInventoryRegistry(registry_path)

    def register(
        self,
        entry: SecretInventoryEntryProfile,
        *,
        replace_existing: bool = False,
        persist: bool = True,
    ) -> SecretInventoryEntryProfile:
        result = self.registry.register(entry, replace=replace_existing)
        if persist:
            self.registry.save()
        return result

    def evaluate_environment(self, environment: str) -> SecretGovernanceProfile:
        return self.engine.evaluate_environment(
            environment,
            self.registry.list_environment(environment),
            self.provider,
        )

    def assert_environment_allowed(self, environment: str) -> SecretGovernanceProfile:
        profile = self.evaluate_environment(environment)
        if not profile.allowed:
            reasons = ", ".join(profile.rejection_reasons) or "UNKNOWN"
            raise RuntimeError(f"Secret governance blocked startup: {reasons}")
        return profile

    def rotate(
        self,
        environment: str,
        name: str,
        new_value: str,
        *,
        new_version: str,
        actor: str,
        reason: str,
        manual_approval: bool = False,
        persist: bool = True,
    ) -> SecretRotationProfile:
        current = self.registry.get(environment, name)
        if current is None:
            raise KeyError(f"Unknown secret inventory entry: {environment}/{name}")

        decision = self.engine.evaluate_rotation(
            current,
            new_value,
            new_version=new_version,
            actor=actor,
            reason=reason,
            manual_approval=manual_approval,
        )
        if not decision.allowed:
            return decision

        now = datetime.now(timezone.utc).isoformat()
        updated = replace(
            current,
            version=str(new_version),
            rotated_at=now,
            fingerprint=decision.new_fingerprint,
        )
        self.registry.register(updated, replace=True)
        self.registry.record_rotation(
            {
                "name": name,
                "environment": environment,
                "previous_version": current.version,
                "new_version": str(new_version),
                "actor": actor,
                "reason": reason,
                "rotated_at": now,
                "promotion_score": decision.promotion_score,
            }
        )
        if persist:
            self.registry.save()
        return decision
