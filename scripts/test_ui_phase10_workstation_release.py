from fastapi.testclient import TestClient

from trading_ai.ui.api.workstation_release import service as release_dependency
from trading_ai.ui.app import create_app
from trading_ai.ui.services.workstation_release_service import (
    WorkstationReleaseService,
)


def main():
    probes = {
        "Dashboard": lambda: True,
        "Opportunities": lambda: True,
        "Symbol Intelligence": lambda: True,
        "Portfolio & Risk": lambda: True,
        "Execution": lambda: True,
        "Reports & Audit": lambda: True,
        "Administration": lambda: True,
        "Identity & Sessions": lambda: True,
    }
    service = WorkstationReleaseService(probes=probes)
    direct = service.get()

    assert direct.summary.release_version == "31.10.0"
    assert direct.summary.overall_status == "READY"
    assert direct.summary.available_modules == 8
    assert direct.summary.unavailable_modules == 0
    assert direct.summary.failing_checks == 0
    assert len(direct.modules) == 8
    assert len(direct.readiness) == 5
    assert all(module.api_path.startswith("/api/v1/") for module in direct.modules)

    app = create_app()
    app.dependency_overrides[release_dependency] = lambda: service

    response = TestClient(app).get("/api/v1/workstation-release")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["overall_status"] == "READY"
    assert payload["summary"]["available_modules"] == 8

    index = TestClient(app).get("/")
    assert index.status_code == 200
    assert "Institutional Workstation" in index.text
    assert "Release Overview" in index.text

    app.dependency_overrides.clear()

    print(
        "All Milestone 31 Phase 10 Workstation Integration, "
        "Navigation, and Release Closure assertions passed."
    )


if __name__ == "__main__":
    main()
