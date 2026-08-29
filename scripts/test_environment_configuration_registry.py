from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from trading_ai.config.environment_registry import EnvironmentConfigurationRegistry, stable_configuration_hash
from trading_ai.config.environment_registry_service import EnvironmentRegistryService
from trading_ai.config.environment_registry_serialization import dumps


@dataclass
class Runtime:
    score: float
    grade: str
    allowed: bool
    recommendation: str = "START"


def main() -> None:
    config = {
        "debug": False,
        "providers": {"broker": "paper", "market_data": "polygon"},
        "trading": {"paper_enabled": True, "live_enabled": False, "kill_switch_enabled": True},
    }
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "config/environment_registry.json"
        service = EnvironmentRegistryService(path)
        dev = service.register_runtime_profile("development", "1.0.0", config, Runtime(96, "A", True), actor="test")
        assert dev.configuration_hash == stable_configuration_hash(config)
        service.registry.activate("development", "1.0.0", actor="test")
        assert service.registry.active("development").version == "1.0.0"

        test_profile, promotion = service.promote(
            "development", "1.0.0", "test", "1.0.0-test",
            target_runtime_score=95,
            target_runtime_allowed=True,
            actor="test",
            reason="validated",
        )
        assert promotion.allowed
        assert promotion.recommendation == "PROMOTE"
        assert test_profile.source_environment == "development"
        assert service.registry.active("test").version == "1.0.0-test"

        paper_profile, paper_promotion = service.promote(
            "test", "1.0.0-test", "paper", "1.0.0-paper",
            target_runtime_score=94,
            target_runtime_allowed=True,
            actor="test",
        )
        assert paper_promotion.allowed
        assert paper_profile.name == "paper"

        rejected = service.evaluate_promotion(
            "paper", "1.0.0-paper", "production",
            target_runtime_score=98,
            target_runtime_allowed=True,
            manual_approval=False,
        )
        assert not rejected.allowed
        assert "MANUAL_PRODUCTION_APPROVAL_REQUIRED" in rejected.rejection_reasons

        production_profile, production_promotion = service.promote(
            "paper", "1.0.0-paper", "production", "1.0.0",
            target_runtime_score=98,
            target_runtime_allowed=True,
            manual_approval=True,
            actor="release-manager",
            reason="approved",
        )
        assert production_promotion.allowed
        assert production_profile.name == "production"

        reloaded = EnvironmentConfigurationRegistry(path)
        assert reloaded.active("production").version == "1.0.0"
        payload = dumps(reloaded.profile())
        assert "release-manager" in payload
        assert "1.0.0-paper" in payload

    print("All environment registry and controlled-promotion assertions passed.")


if __name__ == "__main__":
    main()
