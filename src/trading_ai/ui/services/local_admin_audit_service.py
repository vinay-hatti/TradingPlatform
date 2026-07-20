from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from trading_ai.ui.security.local_admin import LocalAdminActor

class LocalAdminAuditService:
    def __init__(self, audit_path: str | Path = "reports/audit/local_admin_events.jsonl"):
        self.audit_path = Path(audit_path)

    def record(self, *, actor: LocalAdminActor, action: str, resource_type: str,
               resource_id: str, confirmation_token: str | None = None,
               details: dict | None = None, severity: str = "HIGH") -> dict:
        event = {
            "event_id": f"local-admin-{uuid4().hex[:16]}",
            "event_time": datetime.now(timezone.utc).isoformat(),
            "event_type": "LOCAL_ADMIN_OVERRIDE",
            "severity": severity,
            "approval_mode": "LOCAL_ADMIN_OVERRIDE",
            "actor_user_id": actor.user_id,
            "actor_session_id": actor.session_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "confirmation_token_present": bool(confirmation_token),
            "details": details or {},
        }
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        return event
