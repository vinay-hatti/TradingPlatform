from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from trading_ai.production_api import ProductionApiSettings, create_production_app


def main() -> None:
    with TemporaryDirectory() as tmp:
        settings = ProductionApiSettings(
            artifact_root=Path(tmp),
            portfolio_registry_file=Path(tmp) / "missing.json",
            api_key="secret",
            require_api_key=True,
            allow_mutations=False,
        )
        client = TestClient(create_production_app(settings))
        assert client.get("/api/v1/platform/overview").status_code == 401
        assert client.get("/api/v1/platform/overview", headers={"X-API-Key": "secret"}).status_code == 200
        response = client.post(
            "/api/v1/platform/workflows/risk",
            headers={"X-API-Key": "secret", "X-Actor": "tester"},
            json={"requested_by": "tester", "reason": "validation", "arguments": []},
        )
        assert response.status_code == 403
    print("Milestone 40 security and mutation assertions passed.")


if __name__ == "__main__":
    main()
