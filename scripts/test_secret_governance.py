from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_ai.config.credential_health_engine import (
    CredentialHealthEngine,
    secret_fingerprint,
)
from trading_ai.config.secret_governance_policy import SecretGovernancePolicy
from trading_ai.config.secret_governance_profile import SecretInventoryEntryProfile
from trading_ai.config.secret_governance_serialization import dumps
from trading_ai.config.secret_governance_service import SecretGovernanceService
from trading_ai.config.secret_inventory_registry import SecretInventoryRegistry
from trading_ai.config.secret_provider import MappingSecretProvider


def main() -> None:
    now = datetime.now(timezone.utc)
    database_value = "postgresql://secure-user:secure-password@localhost/trading_ai"
    polygon_value = "polygon-production-api-key"

    database_entry = SecretInventoryEntryProfile(
        name="DATABASE_URL",
        environment="production",
        provider="mapping",
        owner="platform-operations",
        created_at=(now - timedelta(days=20)).isoformat(),
        rotated_at=(now - timedelta(days=20)).isoformat(),
        expires_at=(now + timedelta(days=70)).isoformat(),
        version="1",
        fingerprint=secret_fingerprint(database_value),
    )
    polygon_entry = SecretInventoryEntryProfile(
        name="POLYGON_API_KEY",
        environment="production",
        provider="mapping",
        owner="market-data-operations",
        created_at=(now - timedelta(days=65)).isoformat(),
        rotated_at=(now - timedelta(days=65)).isoformat(),
        expires_at=(now + timedelta(days=10)).isoformat(),
        version="4",
        fingerprint=secret_fingerprint(polygon_value),
    )

    provider = MappingSecretProvider(
        {
            "DATABASE_URL": database_value,
            "POLYGON_API_KEY": polygon_value,
        }
    )
    policy = SecretGovernancePolicy()
    engine = CredentialHealthEngine(policy)

    database_health = engine.evaluate_credential(database_entry, provider, now=now)
    assert database_health.allowed
    assert database_health.recommendation == "USE"
    assert database_health.provider == "mapping"

    polygon_health = engine.evaluate_credential(polygon_entry, provider, now=now)
    assert polygon_health.allowed
    assert polygon_health.recommendation == "ROTATE_SOON"
    assert "SECRET_ROTATION_APPROACHING" in polygon_health.warnings
    assert "SECRET_EXPIRY_APPROACHING" in polygon_health.warnings

    aggregate = engine.evaluate_environment(
        "production",
        [database_entry, polygon_entry],
        provider,
        now=now,
    )
    assert aggregate.valid
    assert aggregate.allowed
    assert aggregate.secret_count == 2
    assert aggregate.warning_count == 1
    serialized = dumps(aggregate)
    assert database_value not in serialized
    assert polygon_value not in serialized

    missing = engine.evaluate_environment(
        "production",
        [database_entry],
        MappingSecretProvider({}),
        now=now,
    )
    assert not missing.allowed
    assert any("PROVIDER_RESOLUTION" in item for item in missing.rejection_reasons)

    reused = engine.evaluate_rotation(
        database_entry,
        database_value,
        new_version="2",
        actor="operator",
        reason="scheduled rotation",
        manual_approval=True,
    )
    assert not reused.allowed
    assert "SECRET_REUSE_DETECTED" in reused.rejection_reasons

    manual_required = engine.evaluate_rotation(
        database_entry,
        "new-production-database-secret-2026",
        new_version="2",
        actor="operator",
        reason="scheduled rotation",
        manual_approval=False,
    )
    assert not manual_required.allowed
    assert (
        "MANUAL_PRODUCTION_ROTATION_APPROVAL_REQUIRED"
        in manual_required.rejection_reasons
    )

    approved = engine.evaluate_rotation(
        database_entry,
        "new-production-database-secret-2026",
        new_version="2",
        actor="operator",
        reason="scheduled rotation",
        manual_approval=True,
    )
    assert approved.allowed
    assert approved.recommendation == "ROTATE"

    with tempfile.TemporaryDirectory() as temp_dir:
        registry_path = Path(temp_dir) / "config/secret_inventory.json"
        service = SecretGovernanceService(
            registry_path,
            policy=policy,
            provider=provider,
        )
        service.register(database_entry)
        service.register(polygon_entry)
        profile = service.assert_environment_allowed("production")
        assert profile.allowed

        rotation = service.rotate(
            "production",
            "DATABASE_URL",
            "new-production-database-secret-2026",
            new_version="2",
            actor="operator",
            reason="scheduled rotation",
            manual_approval=True,
        )
        assert rotation.allowed
        reloaded = SecretInventoryRegistry(registry_path)
        updated = reloaded.get("production", "DATABASE_URL")
        assert updated is not None
        assert updated.version == "2"
        assert updated.fingerprint == rotation.new_fingerprint
        assert len(reloaded.rotation_history) == 1

    print("All secret-rotation, governance and credential-health assertions passed.")


if __name__ == "__main__":
    main()
