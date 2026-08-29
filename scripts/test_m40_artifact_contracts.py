from pathlib import Path
from tempfile import TemporaryDirectory
import json

from fastapi.testclient import TestClient

from trading_ai.production_api import ProductionApiSettings, create_production_app


def main() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = root / "registry.json"
        registry.write_text(json.dumps({"portfolio_id": "PRIMARY", "positions": []}), encoding="utf-8")
        for relative, payload in {
            "m37/execution_risk_control.json": {"trading_control": "ALLOW"},
            "m38/execution_queue.json": {"orders": []},
            "m39/position_assessments.json": {"assessments": []},
            "m39/exit_instructions.json": {"instructions": []},
        }.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
        client = TestClient(create_production_app(ProductionApiSettings(artifact_root=root, portfolio_registry_file=registry, max_artifact_age_seconds=999999)))
        for endpoint in ("portfolio", "risk", "execution", "positions", "exit-instructions"):
            response = client.get(f"/api/v1/platform/{endpoint}")
            assert response.status_code == 200, endpoint
            body = response.json()
            assert body["status"] == "ok"
            assert "artifact_path" in body["metadata"]
        assert (root / "m40/api_audit.json").exists()
    print("Milestone 40 artifact contract assertions passed.")


if __name__ == "__main__":
    main()
