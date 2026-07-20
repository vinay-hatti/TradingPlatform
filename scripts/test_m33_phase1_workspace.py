from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient

from trading_ai.ui.api.workspaces import router, service
from trading_ai.ui.services.workspace_service import WorkspaceService


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        workspace_service = WorkspaceService(
            root / "workspaces.json",
            root / "notifications.json",
        )
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[service] = lambda: workspace_service
        client = TestClient(app)

        created = client.post(
            "/api/v1/workspaces",
            json={"name": "Trading Desk", "owner": "tester", "template": "trading"},
        )
        assert created.status_code == 200
        workspace = created.json()
        assert len(workspace["panels"]) == 4

        listed = client.get("/api/v1/workspaces?owner=tester")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        updated = client.put(
            f"/api/v1/workspaces/{workspace['workspace_id']}",
            json={
                "theme": "light",
                "active_view": "paper-commands",
                "expected_version": workspace["version"],
            },
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2
        assert updated.json()["theme"] == "light"

        conflict = client.put(
            f"/api/v1/workspaces/{workspace['workspace_id']}",
            json={"theme": "dark", "expected_version": 1},
        )
        assert conflict.status_code == 409

        commands = client.get("/api/v1/workspaces/commands")
        assert commands.status_code == 200
        assert any(item["command_id"] == "workspace-save" for item in commands.json())

        note = client.post(
            "/api/v1/workspaces/notifications",
            json={"severity": "WARNING", "title": "Test", "message": "Test warning"},
        )
        assert note.status_code == 200
        note_id = note.json()["notification_id"]

        acknowledged = client.post(
            f"/api/v1/workspaces/notifications/{note_id}/acknowledge",
            json={},
        )
        assert acknowledged.status_code == 200
        assert acknowledged.json()["acknowledged"] is True

    print(
        "All Milestone 33 Phase 1 Interactive Workspace Foundation "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
