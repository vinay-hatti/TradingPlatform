from __future__ import annotations

import json
import tempfile
from pathlib import Path

from trading_ai.config.production_configuration import ProductionConfigurationLoader
from trading_ai.config.production_runtime_engine import ProductionRuntimeSafetyEngine
from trading_ai.config.production_runtime_policy import ProductionRuntimePolicy
from trading_ai.config.production_runtime_serialization import dumps
from trading_ai.config.production_runtime_service import ProductionRuntimeSafetyService
from trading_ai.config.secret_provider import MappingSecretProvider


def write_config(root: Path, environment: str, payload: dict) -> None:
    config = root / "config"
    config.mkdir(parents=True, exist_ok=True)
    (config / f"runtime.{environment}.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "config").mkdir()
        (root / "config/runtime.json").write_text(
            json.dumps(
                {
                    "debug": False,
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
                    "feature_flags": {"runtime_safety": True},
                }
            ),
            encoding="utf-8",
        )

        write_config(
            root,
            "production",
            {
                "debug": False,
                "database_url": "${DATABASE_URL}",
                "providers": {
                    "broker": "paper",
                    "market_data": "polygon",
                },
                "required_secrets": ["DATABASE_URL", "POLYGON_API_KEY"],
                "trading": {
                    "paper_enabled": True,
                    "live_enabled": False,
                    "kill_switch_enabled": True,
                },
            },
        )

        loader = ProductionConfigurationLoader(root)
        config = loader.load(environment="production")
        assert config.environment == "production"
        assert config.data_directory == "data"
        assert config.market_data_provider == "polygon"

        provider = MappingSecretProvider(
            {
                "DATABASE_URL": "postgresql://user:password@localhost/trading_ai",
                "POLYGON_API_KEY": "polygon-secret",
            }
        )
        policy = ProductionRuntimePolicy(
            required_feature_flags={"runtime_safety": True}
        )
        profile = ProductionRuntimeSafetyEngine(policy).evaluate(
            config,
            provider,
            raw_configuration={"database_url": "${DATABASE_URL}"},
        )
        assert profile.valid
        assert profile.allowed
        assert profile.recommendation == "START"
        assert profile.configuration["database_url"] == "<redacted>"
        assert all(secret.resolved for secret in profile.resolved_secrets)
        assert "polygon-secret" not in dumps(profile)

        blocked = ProductionRuntimeSafetyEngine(policy).evaluate(
            config,
            MappingSecretProvider({}),
            raw_configuration={"database_url": "plaintext-password"},
        )
        assert not blocked.allowed
        assert blocked.recommendation == "BLOCK_STARTUP"
        assert "REQUIRED_SECRETS" in blocked.rejection_reasons
        assert "PLAINTEXT_SECRETS" in blocked.rejection_reasons

        service = ProductionRuntimeSafetyService(
            project_root=root,
            policy=policy,
            secret_provider=provider,
        )
        assert service.assert_startup_allowed("production").allowed

    print("All aligned production configuration and runtime-safety assertions passed.")


if __name__ == "__main__":
    main()
