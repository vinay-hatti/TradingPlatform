from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.api.auth_session import service as auth_dependency
from trading_ai.ui.app import create_app
from trading_ai.ui.models.auth_session import SessionActionRequest
from trading_ai.ui.services.auth_session_service import AuthSessionService


def main():
    now = datetime.now(timezone.utc)

    with TemporaryDirectory() as directory:
        root = Path(directory)
        security = root / "reports/security"
        security.mkdir(parents=True)

        (security / "active_session.json").write_text(
            json.dumps({
                "sessions": [
                    {
                        "session_id": "S1",
                        "user_id": "vinay",
                        "display_name": "Vinay Hatti",
                        "authentication_method": "LOCAL",
                        "authenticated_at": (
                            now - timedelta(minutes=10)
                        ).isoformat(),
                        "last_activity_at": (
                            now - timedelta(minutes=1)
                        ).isoformat(),
                        "expires_at": (
                            now + timedelta(hours=2)
                        ).isoformat(),
                        "active": True,
                    }
                ]
            }),
            encoding="utf-8",
        )

        (security / "role_assignments.json").write_text(
            json.dumps({
                "roles": [
                    {
                        "role": "TRADER",
                        "scope": "paper",
                        "active": True,
                    },
                    {
                        "role": "AUDITOR",
                        "scope": "global",
                        "active": True,
                    },
                ]
            }),
            encoding="utf-8",
        )

        (security / "permission_grants.json").write_text(
            json.dumps({
                "permissions": [
                    {
                        "permission": "orders.cancel",
                        "allowed": True,
                        "scope": "paper",
                    },
                    {
                        "permission": "live_trading.enable",
                        "allowed": False,
                        "scope": "production",
                        "reason": "Production access is not authorized.",
                    },
                ]
            }),
            encoding="utf-8",
        )

        (security / "authentication_events.json").write_text(
            json.dumps({
                "events": [
                    {
                        "event_id": "E1",
                        "occurred_at": now.isoformat(),
                        "event_type": "LOGIN",
                        "outcome": "SUCCESS",
                        "actor": "vinay",
                        "ip_address": "127.0.0.1",
                        "detail": "Interactive login completed.",
                    }
                ]
            }),
            encoding="utf-8",
        )

        service = AuthSessionService(
            RepositoryArtifactAdapters(root),
            idle_timeout_seconds=1800,
        )
        direct = service.get()

        assert direct.available is True
        assert direct.identity is not None
        assert direct.identity.user_id == "vinay"
        assert direct.governance.authenticated is True
        assert direct.governance.active is True
        assert direct.governance.expired is False
        assert direct.governance.idle is False
        assert direct.governance.session_status == "ACTIVE"
        assert direct.governance.active_role_count == 2
        assert direct.governance.denied_permission_count == 1
        assert direct.governance.privileged is True
        assert direct.governance.enforcement_mode == "DENY_BY_DEFAULT"

        action = service.action(
            "terminate",
            "S1",
            SessionActionRequest(),
        )
        assert action.accepted is False

        app = create_app()
        app.dependency_overrides[auth_dependency] = lambda: service

        response = TestClient(app).get("/api/v1/auth-session")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["identity"]["user_id"] == "vinay"
        assert payload["governance"]["session_status"] == "ACTIVE"
        assert payload["governance"]["denied_permission_count"] == 1

        app.dependency_overrides.clear()

    print(
        "All Milestone 31 Phase 9 Authentication, Authorization, "
        "and User Session Governance assertions passed."
    )


if __name__ == "__main__":
    main()
