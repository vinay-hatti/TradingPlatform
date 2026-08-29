from __future__ import annotations

from fastapi.testclient import TestClient

from trading_ai.ui.app import create_app


def main() -> None:
    app = create_app()
    client = TestClient(app)

    health = client.get("/api/v1/health")
    assert health.status_code == 200, health.text

    dashboard = client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    payload = dashboard.json()
    assert "metrics" in payload
    assert "system_health" in payload

    index = client.get("/")
    assert index.status_code == 200, index.text

    print("All Trading AI UI import and route assertions passed.")


if __name__ == "__main__":
    main()
