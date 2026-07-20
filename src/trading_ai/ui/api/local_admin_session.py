from fastapi import APIRouter, HTTPException
from trading_ai.ui.security.local_admin import current_local_admin, local_admin_enabled

router = APIRouter(prefix="/api/v1/session", tags=["local-admin-session"])

@router.get("/current")
def current_session():
    if not local_admin_enabled():
        return {"authenticated": False, "local_admin_mode": False, "user_id": None,
                "display_name": "Read-Only Workstation", "session_id": None,
                "roles": [], "permissions": []}
    try:
        actor = current_local_admin()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    payload = actor.model_dump()
    payload["authenticated"] = True
    return payload
