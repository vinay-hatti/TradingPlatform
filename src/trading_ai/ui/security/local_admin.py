from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Iterable
from trading_ai.config.settings import settings

LOCAL_ADMIN_PERMISSIONS = (
    "security.identity.create","security.role.manage","security.entitlement.request",
    "security.entitlement.approve","security.entitlement.apply","security.session.revoke",
    "security.secret.metadata","security.access_review.create",
    "operations.runtime.request","operations.runtime.approve","operations.runtime.execute",
    "operations.release.register","operations.lock.acquire",
    "strategy.version.create","strategy.experiment.create","strategy.experiment.execute",
    "strategy.experiment.promote","strategy.shadow.deploy",
    "portfolio.read","portfolio.manage","research.read","research.execute",
    "executive.read","compliance.read","audit.read",
)
LOCAL_ADMIN_ROLES = (
    "PLATFORM_SUPER_ADMIN","SECURITY_ADMIN","SECURITY_APPROVER","OPERATIONS_ADMIN",
    "STRATEGY_ADMIN","PORTFOLIO_ADMIN","RESEARCH_ADMIN",
)

@dataclass(frozen=True)
class LocalAdminActor:
    user_id: str
    display_name: str
    session_id: str
    local_admin_mode: bool
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions
    def has_all_permissions(self, permissions: Iterable[str]) -> bool:
        return all(p in self.permissions for p in permissions)
    def model_dump(self) -> dict:
        payload = asdict(self)
        payload["roles"] = list(self.roles)
        payload["permissions"] = list(self.permissions)
        return payload

def local_admin_enabled() -> bool:
    return bool(getattr(settings, "ui_local_admin_mode", False))

def require_localhost_bind() -> None:
    if not local_admin_enabled():
        return
    host = str(getattr(settings, "ui_bind_host", "127.0.0.1")).strip().lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError(
            "UI_LOCAL_ADMIN_MODE requires UI_BIND_HOST to be localhost-only "
            "(127.0.0.1, localhost, or ::1)."
        )

def current_local_admin() -> LocalAdminActor:
    require_localhost_bind()
    if not local_admin_enabled():
        raise RuntimeError("Local workstation administrator mode is disabled.")
    user_id = str(getattr(settings, "ui_local_admin_user_id", "local-workstation-admin")).strip()
    display_name = str(getattr(settings, "ui_local_admin_display_name",
                               "Local Workstation Administrator")).strip()
    return LocalAdminActor(
        user_id=user_id or "local-workstation-admin",
        display_name=display_name or "Local Workstation Administrator",
        session_id="local-workstation-session",
        local_admin_mode=True,
        roles=LOCAL_ADMIN_ROLES,
        permissions=LOCAL_ADMIN_PERMISSIONS,
    )
