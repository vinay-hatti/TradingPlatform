from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class SessionIdentity(BaseModel):
    session_id: str
    user_id: str
    display_name: str
    authentication_method: str = "UNKNOWN"
    authenticated_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    source: str = ""


class RoleAssignment(BaseModel):
    role: str
    scope: str = "global"
    active: bool = True
    source: str = ""


class PermissionGrant(BaseModel):
    permission: str
    allowed: bool
    scope: str = "global"
    reason: str = ""
    source: str = ""


class AuthenticationEvent(BaseModel):
    event_id: str
    occurred_at: datetime
    event_type: str
    outcome: str
    actor: str
    ip_address: str | None = None
    detail: str = ""
    source: str = ""


class SessionGovernance(BaseModel):
    authenticated: bool = False
    active: bool = False
    expired: bool = True
    idle: bool = True
    idle_seconds: float | None = None
    expires_in_seconds: float | None = None
    privileged: bool = False
    denied_permission_count: int = 0
    active_role_count: int = 0
    session_status: str = "UNAUTHENTICATED"
    enforcement_mode: str = "DENY_BY_DEFAULT"


class AuthSessionResponse(BaseModel):
    generated_at: datetime
    available: bool
    source_detail: str
    governance: SessionGovernance
    identity: SessionIdentity | None = None
    roles: list[RoleAssignment] = Field(default_factory=list)
    permissions: list[PermissionGrant] = Field(default_factory=list)
    events: list[AuthenticationEvent] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)


class SessionActionRequest(BaseModel):
    reason: str = "Requested from institutional workstation"


class SessionActionResult(BaseModel):
    accepted: bool
    action: str
    session_id: str
    message: str
    requested_at: datetime
