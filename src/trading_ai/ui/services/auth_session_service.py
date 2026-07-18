from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.models.auth_session import (
    AuthenticationEvent,
    AuthSessionResponse,
    PermissionGrant,
    RoleAssignment,
    SessionActionRequest,
    SessionActionResult,
    SessionGovernance,
    SessionIdentity,
)


def val(row: Any, *names: str, default=None):
    for name in names:
        candidate = row.get(name) if isinstance(row, dict) else getattr(row, name, None)
        if candidate not in (None, ""):
            return candidate
    return default


def parse_datetime(raw: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if raw not in (None, ""):
        try:
            parsed = datetime.fromisoformat(
                str(raw).strip().replace("Z", "+00:00")
            )
            return (
                parsed
                if parsed.tzinfo
                else parsed.replace(tzinfo=timezone.utc)
            )
        except ValueError:
            pass
    return fallback or datetime.now(timezone.utc)


class SessionCommandService(Protocol):
    def execute(
        self,
        action: str,
        session_id: str,
        reason: str,
    ) -> Any:
        ...


class AuthSessionService:
    SESSION_PATTERNS = (
        "security/**/*session*.json",
        "auth/**/*session*.json",
        "runtime/**/*session*.json",
        "**/active_session*.json",
        "**/user_session*.json",
    )
    ROLE_PATTERNS = (
        "security/**/*role*.json",
        "auth/**/*role*.json",
        "**/role_assignments*.json",
        "**/rbac*.json",
    )
    PERMISSION_PATTERNS = (
        "security/**/*permission*.json",
        "auth/**/*permission*.json",
        "**/permission_grants*.json",
        "**/authorization*.json",
    )
    EVENT_PATTERNS = (
        "security/**/*auth*event*.json",
        "auth/**/*event*.json",
        "audit/**/*authentication*.json",
        "**/authentication_events*.json",
        "**/security_events*.json",
    )

    PRIVILEGED_PERMISSIONS = {
        "orders.cancel",
        "orders.replace",
        "runtime.control",
        "configuration.write",
        "live_trading.enable",
        "broker.credentials.manage",
    }

    def __init__(
        self,
        artifacts: RepositoryArtifactAdapters | None = None,
        commands: SessionCommandService | None = None,
        idle_timeout_seconds: int = 1800,
        default_session_seconds: int = 8 * 3600,
    ):
        self.artifacts = artifacts or RepositoryArtifactAdapters()
        self.commands = commands
        self.idle_timeout_seconds = idle_timeout_seconds
        self.default_session_seconds = default_session_seconds

    @property
    def root(self) -> Path:
        return self.artifacts.root

    @property
    def reports_root(self) -> Path:
        return self.root / "reports"

    def _files(self, patterns: tuple[str, ...]) -> list[Path]:
        found: dict[str, Path] = {}
        for pattern in patterns:
            for path in self.reports_root.glob(pattern):
                if path.is_file():
                    found[str(path.resolve())] = path
        return sorted(
            found.values(),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    @staticmethod
    def _read(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _rows(payload: Any, *keys: str) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in keys:
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    return [
                        item for item in candidate
                        if isinstance(item, dict)
                    ]
            return [payload] if payload else []
        return []

    @staticmethod
    def _file_time(path: Path) -> datetime:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

    def _latest(
        self,
        patterns: tuple[str, ...],
        validator=None,
    ) -> tuple[Any, Path | None]:
        for path in self._files(patterns):
            try:
                payload = self._read(path)
            except Exception:
                continue
            if validator is None or validator(payload):
                return payload, path
        return {}, None

    @classmethod
    def _session_payload(cls, payload: Any) -> bool:
        rows = cls._rows(payload, "sessions", "active_sessions", "items")
        return any(
            val(row, "session_id", "id")
            and val(row, "user_id", "username", "principal")
            for row in rows
        )

    def _identity(
        self,
        payload: Any,
        path: Path | None,
    ) -> SessionIdentity | None:
        rows = self._rows(
            payload,
            "sessions",
            "active_sessions",
            "items",
        )
        if not rows:
            return None

        row = next(
            (
                item for item in rows
                if bool(val(item, "active", "is_active", default=True))
            ),
            rows[0],
        )
        fallback = self._file_time(path) if path else datetime.now(timezone.utc)
        authenticated_at = parse_datetime(
            val(
                row,
                "authenticated_at",
                "created_at",
                "login_at",
            ),
            fallback=fallback,
        )
        last_activity_at = parse_datetime(
            val(
                row,
                "last_activity_at",
                "last_seen_at",
                "updated_at",
            ),
            fallback=authenticated_at,
        )
        expires_at_raw = val(
            row,
            "expires_at",
            "expiration",
            "expiry_at",
        )
        expires_at = (
            parse_datetime(expires_at_raw)
            if expires_at_raw not in (None, "")
            else authenticated_at
            + timedelta(seconds=self.default_session_seconds)
        )

        return SessionIdentity(
            session_id=str(val(row, "session_id", "id")),
            user_id=str(
                val(
                    row,
                    "user_id",
                    "username",
                    "principal",
                )
            ),
            display_name=str(
                val(
                    row,
                    "display_name",
                    "name",
                    default=val(
                        row,
                        "user_id",
                        "username",
                        "principal",
                    ),
                )
            ),
            authentication_method=str(
                val(
                    row,
                    "authentication_method",
                    "auth_method",
                    "provider",
                    default="UNKNOWN",
                )
            ).upper(),
            authenticated_at=authenticated_at,
            last_activity_at=last_activity_at,
            expires_at=expires_at,
            source=str(path.relative_to(self.root)) if path else "",
        )

    def _roles(
        self,
        payload: Any,
        path: Path | None,
    ) -> list[RoleAssignment]:
        roles = []
        for row in self._rows(
            payload,
            "roles",
            "assignments",
            "items",
        ):
            role = str(
                val(
                    row,
                    "role",
                    "name",
                    "role_name",
                    default="",
                )
            ).strip()
            if not role:
                continue
            roles.append(
                RoleAssignment(
                    role=role,
                    scope=str(val(row, "scope", default="global")),
                    active=bool(
                        val(
                            row,
                            "active",
                            "enabled",
                            default=True,
                        )
                    ),
                    source=str(path.relative_to(self.root)) if path else "",
                )
            )
        return roles

    def _permissions(
        self,
        payload: Any,
        path: Path | None,
    ) -> list[PermissionGrant]:
        permissions = []
        for row in self._rows(
            payload,
            "permissions",
            "grants",
            "items",
        ):
            permission = str(
                val(
                    row,
                    "permission",
                    "name",
                    "action",
                    default="",
                )
            ).strip()
            if not permission:
                continue
            permissions.append(
                PermissionGrant(
                    permission=permission,
                    allowed=bool(
                        val(
                            row,
                            "allowed",
                            "granted",
                            "enabled",
                            default=False,
                        )
                    ),
                    scope=str(val(row, "scope", default="global")),
                    reason=str(
                        val(
                            row,
                            "reason",
                            "detail",
                            default="",
                        )
                    ),
                    source=str(path.relative_to(self.root)) if path else "",
                )
            )
        return permissions

    def _events(
        self,
        paths: list[Path],
    ) -> list[AuthenticationEvent]:
        events = []
        for path in paths[:25]:
            try:
                payload = self._read(path)
            except Exception:
                continue
            for index, row in enumerate(
                self._rows(
                    payload,
                    "events",
                    "authentication_events",
                    "items",
                )
            ):
                events.append(
                    AuthenticationEvent(
                        event_id=str(
                            val(
                                row,
                                "event_id",
                                "id",
                                default=f"{path.stem}-{index}",
                            )
                        ),
                        occurred_at=parse_datetime(
                            val(
                                row,
                                "occurred_at",
                                "timestamp",
                                "created_at",
                            ),
                            self._file_time(path),
                        ),
                        event_type=str(
                            val(
                                row,
                                "event_type",
                                "type",
                                "action",
                                default="AUTH_EVENT",
                            )
                        ).upper(),
                        outcome=str(
                            val(
                                row,
                                "outcome",
                                "status",
                                "result",
                                default="UNKNOWN",
                            )
                        ).upper(),
                        actor=str(
                            val(
                                row,
                                "actor",
                                "user_id",
                                "username",
                                default="system",
                            )
                        ),
                        ip_address=(
                            str(
                                val(
                                    row,
                                    "ip_address",
                                    "source_ip",
                                    default="",
                                )
                            )
                            or None
                        ),
                        detail=str(
                            val(
                                row,
                                "detail",
                                "message",
                                "reason",
                                default="",
                            )
                        ),
                        source=str(path.relative_to(self.root)),
                    )
                )
        return sorted(
            events,
            key=lambda item: item.occurred_at,
            reverse=True,
        )[:250]

    def get(self) -> AuthSessionResponse:
        session_payload, session_path = self._latest(
            self.SESSION_PATTERNS,
            validator=self._session_payload,
        )
        role_payload, role_path = self._latest(self.ROLE_PATTERNS)
        permission_payload, permission_path = self._latest(
            self.PERMISSION_PATTERNS
        )
        event_paths = self._files(self.EVENT_PATTERNS)

        identity = self._identity(session_payload, session_path)
        roles = self._roles(role_payload, role_path)
        permissions = self._permissions(
            permission_payload,
            permission_path,
        )
        events = self._events(event_paths)

        now = datetime.now(timezone.utc)
        authenticated = identity is not None
        expired = True
        idle = True
        idle_seconds = None
        expires_in_seconds = None

        if identity is not None:
            idle_seconds = max(
                0.0,
                (now - identity.last_activity_at).total_seconds(),
            )
            expires_in_seconds = (
                identity.expires_at - now
            ).total_seconds()
            expired = expires_in_seconds <= 0
            idle = idle_seconds > self.idle_timeout_seconds

        active = authenticated and not expired and not idle
        active_roles = [item for item in roles if item.active]
        denied = [item for item in permissions if not item.allowed]
        privileged = any(
            item.allowed
            and item.permission in self.PRIVILEGED_PERMISSIONS
            for item in permissions
        )

        if not authenticated:
            session_status = "UNAUTHENTICATED"
        elif expired:
            session_status = "EXPIRED"
        elif idle:
            session_status = "IDLE_TIMEOUT"
        elif active:
            session_status = "ACTIVE"
        else:
            session_status = "INACTIVE"

        notices = []
        if identity is None:
            notices.append("No authenticated user session was found.")
        if not roles:
            notices.append("No role assignments were found.")
        if not permissions:
            notices.append(
                "No permission grants were found; privileged actions "
                "must be denied by default."
            )
        if self.commands is None:
            notices.append(
                "Session actions are read-only because no governed "
                "session command service is configured."
            )
        if denied:
            notices.append(
                f"{len(denied)} explicit permission denials are active."
            )

        paths = [
            path
            for path in (
                session_path,
                role_path,
                permission_path,
                *event_paths[:5],
            )
            if path is not None
        ]

        return AuthSessionResponse(
            generated_at=now,
            available=bool(
                session_payload
                or role_payload
                or permission_payload
                or events
            ),
            source_detail=(
                "; ".join(
                    str(path.relative_to(self.root))
                    for path in paths
                )
                or "No authentication artifacts available."
            ),
            governance=SessionGovernance(
                authenticated=authenticated,
                active=active,
                expired=expired,
                idle=idle,
                idle_seconds=(
                    round(idle_seconds, 2)
                    if idle_seconds is not None
                    else None
                ),
                expires_in_seconds=(
                    round(expires_in_seconds, 2)
                    if expires_in_seconds is not None
                    else None
                ),
                privileged=privileged,
                denied_permission_count=len(denied),
                active_role_count=len(active_roles),
                session_status=session_status,
                enforcement_mode="DENY_BY_DEFAULT",
            ),
            identity=identity,
            roles=roles,
            permissions=permissions,
            events=events,
            notices=notices,
        )

    def action(
        self,
        action: str,
        session_id: str,
        request: SessionActionRequest,
    ) -> SessionActionResult:
        now = datetime.now(timezone.utc)
        if self.commands is None:
            return SessionActionResult(
                accepted=False,
                action=action.upper(),
                session_id=session_id,
                message=(
                    "Session governance is read-only; governed command "
                    "service is not configured."
                ),
                requested_at=now,
            )

        result = self.commands.execute(
            action=action,
            session_id=session_id,
            reason=request.reason,
        )
        return SessionActionResult(
            accepted=True,
            action=action.upper(),
            session_id=session_id,
            message=str(result),
            requested_at=now,
        )
