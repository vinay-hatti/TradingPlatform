from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_ai.config.environment_profile import EnvironmentProfile
from trading_ai.config.environment_registry import EnvironmentConfigurationRegistry
from trading_ai.config.production_configuration import ProductionConfigurationLoader
from trading_ai.config.production_runtime_engine import ProductionRuntimeSafetyEngine
from trading_ai.config.secret_governance_profile import SecretGovernanceProfile
from trading_ai.config.startup_readiness_engine import StartupReadinessEngine
from trading_ai.config.startup_readiness_policy import StartupReadinessPolicy
from trading_ai.config.startup_readiness_serialization import dumps
from trading_ai.config.startup_readiness_service import configuration_fingerprint


def main() -> None:
    policy = StartupReadinessPolicy()
    engine = StartupReadinessEngine(policy)

    runtime = {
        "allowed": True,
        "score": 100.0,
        "grade": "A",
        "severity": "LOW",
    }
    secrets = SecretGovernanceProfile(
        valid=True,
        allowed=True,
        environment="production",
        secret_count=2,
        healthy_count=2,
        warning_count=0,
        rejected_count=0,
        score=100.0,
        grade="A",
        severity="LOW",
        recommendation="START",
    )
    fingerprint = "abc123"
    environment = {
        "allowed": True,
        "active": True,
        "version": "prod-2026.07.14",
        "runtime_score": 100.0,
        "configuration_fingerprint": fingerprint,
    }

    approved = engine.evaluate(
        environment="production",
        configuration_fingerprint=fingerprint,
        runtime_profile=runtime,
        environment_registry_profile=environment,
        secret_governance_profile=secrets,
    )
    assert approved.allowed
    assert approved.recommendation == "START"
    assert approved.score == 100.0
    assert approved.active_environment_version == "prod-2026.07.14"
    assert "abc123" in dumps(approved)

    mismatch = engine.evaluate(
        environment="production",
        configuration_fingerprint="different",
        runtime_profile=runtime,
        environment_registry_profile=environment,
        secret_governance_profile=secrets,
    )
    assert not mismatch.allowed
    assert "CONFIGURATION_FINGERPRINT" in mismatch.rejection_reasons

    blocked_secrets = asdict(secrets)
    blocked_secrets["allowed"] = False
    blocked_secrets["score"] = 50.0
    rejected = engine.evaluate(
        environment="production",
        configuration_fingerprint=fingerprint,
        runtime_profile=runtime,
        environment_registry_profile=environment,
        secret_governance_profile=blocked_secrets,
    )
    assert not rejected.allowed
    assert "SECRET_GOVERNANCE" in rejected.rejection_reasons

    missing_registry = engine.evaluate(
        environment="production",
        configuration_fingerprint=fingerprint,
        runtime_profile=runtime,
        environment_registry_profile=None,
        secret_governance_profile=secrets,
    )
    assert not missing_registry.allowed
    assert "ENVIRONMENT_REGISTRY" in missing_registry.rejection_reasons
    assert "ACTIVE_ENVIRONMENT_VERSION" in missing_registry.rejection_reasons

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "config").mkdir(parents=True)
        (root / "config/runtime.json").write_text(
            json.dumps(
                {
                    "debug": False,
                    "database_url": "${DATABASE_URL}",
                    "providers": {
                        "broker": "paper",
                        "market_data": "polygon",
                    },
                    "paths": {
                        "data": "data",
                        "reports": "reports",
                        "logs": "logs",
                        "audit": "logs/audit",
                    },
                    "trading": {
                        "paper_enabled": True,
                        "live_enabled": False,
                        "kill_switch_enabled": True,
                    },
                    "required_secrets": [],
                }
            ),
            encoding="utf-8",
        )
        config = ProductionConfigurationLoader(root).load("production")
        calculated = configuration_fingerprint(config)
        assert len(calculated) == 64
        assert calculated == configuration_fingerprint(config)

    print("All startup orchestration and readiness-gate assertions passed.")


if __name__ == "__main__":
    main()
