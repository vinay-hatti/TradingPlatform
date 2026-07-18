from fastapi import APIRouter, Depends

from trading_ai.ui.models.auth_session import (
    AuthSessionResponse,
    SessionActionRequest,
    SessionActionResult,
)
from trading_ai.ui.services.auth_session_service import AuthSessionService

router = APIRouter(prefix="/api/v1/auth-session", tags=["auth-session"])


def service() -> AuthSessionService:
    return AuthSessionService()


@router.get("", response_model=AuthSessionResponse)
def auth_session(
    center: AuthSessionService = Depends(service),
):
    return center.get()


@router.post(
    "/actions/{action}/{session_id}",
    response_model=SessionActionResult,
)
def session_action(
    action: str,
    session_id: str,
    request: SessionActionRequest,
    center: AuthSessionService = Depends(service),
):
    return center.action(action, session_id, request)
