from pathlib import Path
from tempfile import TemporaryDirectory
import json

from fastapi.testclient import TestClient

from trading_ai.production_api import ProductionApiSettings, create_production_app


def main() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = root / "registry.json"
        risk = root / "m37/execution_risk_control.json"
        registry.write_text(json.dumps({"portfolio_id": "PRIMARY"}), encoding="utf-8")
        risk.parent.mkdir(parents=True)
        risk.write_text(json.dumps({"trading_control": "ALLOW"}), encoding="utf-8")
        settings = ProductionApiSettings(artifact_root=root, portfolio_registry_file=registry, max_artifact_age_seconds=999999)
        client = TestClient(create_production_app(settings))
        health = client.get("/api/v1/platform/health")
        assert health.status_code == 200
        assert health.headers.get("X-Request-ID")
        readiness = client.get("/api/v1/platform/readiness")
        assert readiness.status_code == 200
        assert readiness.json()["data"]["ready"] is True
    print("Milestone 40 health and readiness assertions passed.")


if __name__ == "__main__":
    main()
