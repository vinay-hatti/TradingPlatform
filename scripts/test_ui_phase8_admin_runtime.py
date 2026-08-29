from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.api.admin_runtime import service as admin_dependency
from trading_ai.ui.app import create_app
from trading_ai.ui.models.admin_runtime import RuntimeControlRequest
from trading_ai.ui.services.admin_runtime_service import AdminRuntimeService


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = root / "reports/config"
        runtime = root / "reports/runtime"
        config.mkdir(parents=True)
        runtime.mkdir(parents=True)

        profile_path = config / "environment_profile.json"
        profile_path.write_text(
            json.dumps({
                "profiles": [
                    {
                        "environment": "PAPER",
                        "profile_name": "paper-safe",
                        "version": "3",
                        "active": True,
                    }
                ]
            }),
            encoding="utf-8",
        )

        # This file is deliberately written after the profile file.
        # It must not be misclassified as an environment profile.
        (config / "feature_flags.json").write_text(
            json.dumps({
                "feature_flags": [
                    {
                        "name": "live_trading",
                        "enabled": False,
                        "scope": "environment",
                    },
                    {
                        "name": "paper_trading",
                        "enabled": True,
                        "scope": "environment",
                    },
                ]
            }),
            encoding="utf-8",
        )

        (runtime / "runtime_health.json").write_text(
            json.dumps({
                "components": [
                    {
                        "name": "database",
                        "status": "HEALTHY",
                        "detail": "Database reachable.",
                        "latency_ms": 12,
                        "readiness": True,
                        "required": True,
                    },
                    {
                        "name": "market-data",
                        "status": "DEGRADED",
                        "detail": "Feed is delayed.",
                        "latency_ms": 2400,
                        "readiness": True,
                        "required": True,
                    },
                ],
                "readiness": [
                    {
                        "name": "broker-authentication",
                        "status": "PASS",
                        "required": True,
                    }
                ],
            }),
            encoding="utf-8",
        )

        (runtime / "configuration_drift.json").write_text(
            json.dumps({
                "drift": [
                    {
                        "key": "pricing.risk_free_rate",
                        "expected": "0.04",
                        "actual": "0.05",
                        "status": "DRIFTED",
                    }
                ]
            }),
            encoding="utf-8",
        )

        service = AdminRuntimeService(
            RepositoryArtifactAdapters(root),
            stale_after_seconds=999999999,
        )
        direct = service.get()

        assert direct.available is True
        assert direct.summary.environment == "PAPER", (
            direct.summary.model_dump()
        )
        assert direct.summary.profile_name == "paper-safe"
        assert direct.profiles[0].source.endswith(
            "reports/config/environment_profile.json"
        )
        assert direct.summary.readiness_status == "DEGRADED"
        assert direct.summary.healthy_components == 1
        assert direct.summary.degraded_components == 1
        assert direct.summary.enabled_feature_flags == 1
        assert direct.summary.disabled_feature_flags == 1
        assert direct.summary.configuration_drift_count == 1
        assert direct.summary.control_mode == "READ_ONLY"

        control = service.control(
            "restart",
            "market-data",
            RuntimeControlRequest(),
        )
        assert control.accepted is False

        app = create_app()
        app.dependency_overrides[admin_dependency] = lambda: service
        response = TestClient(app).get("/api/v1/admin-runtime")
        assert response.status_code == 200, response.text

        payload = response.json()
        assert payload["summary"]["environment"] == "PAPER"
        assert payload["summary"]["profile_name"] == "paper-safe"
        assert payload["summary"]["readiness_status"] == "DEGRADED"

        app.dependency_overrides.clear()

    print(
        "All corrected Milestone 31 Phase 8 Administration and "
        "Runtime Control Center assertions passed."
    )


if __name__ == "__main__":
    main()
