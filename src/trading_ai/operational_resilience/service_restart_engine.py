from __future__ import annotations
from datetime import datetime, timezone
from typing import Callable
import hashlib

from .recovery_policy import ServiceRestartPolicy
from .recovery_profile import ServiceRestartRecord

def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

class ServiceRestartEngine:
    def __init__(
        self, policy: ServiceRestartPolicy | None = None
    ) -> None:
        self.policy = policy or ServiceRestartPolicy()
        self.policy.validate()

    def authorize(
        self,
        *,
        service_name: str,
        instance_id: str,
        environment: str,
        reason: str,
        requested_by: str,
        critical: bool,
        prior_restarts: tuple[ServiceRestartRecord, ...],
        as_of: datetime | None = None,
    ) -> ServiceRestartRecord:
        now = as_of or datetime.now(timezone.utc)
        within_window = tuple(
            item for item in prior_restarts
            if (
                now - _parse(item.requested_at)
            ).total_seconds() <= self.policy.restart_window_seconds
        )
        latest = max(
            prior_restarts,
            key=lambda item: item.requested_at,
            default=None,
        )
        allowed = self.policy.allow_automatic_restart
        failure = None
        if (
            critical
            and self.policy.require_manual_approval_for_critical_services
        ):
            allowed = False
            failure = "MANUAL_APPROVAL_REQUIRED"
        elif len(within_window) >= self.policy.maximum_restarts_per_window:
            allowed = False
            failure = "RESTART_RATE_LIMIT_EXCEEDED"
        elif latest and (
            now - _parse(latest.requested_at)
        ).total_seconds() < self.policy.minimum_restart_interval_seconds:
            allowed = False
            failure = "RESTART_COOLDOWN_ACTIVE"

        restart_id = "restart-" + hashlib.sha256(
            f"{service_name}:{instance_id}:{now.isoformat()}".encode()
        ).hexdigest()[:16]
        return ServiceRestartRecord(
            restart_id=restart_id,
            service_name=service_name,
            instance_id=instance_id,
            environment=environment,
            reason=reason,
            requested_by=requested_by,
            approved=allowed,
            status="APPROVED" if allowed else "REJECTED",
            critical=critical,
            requested_at=now.isoformat(),
            failure_message=failure,
        )

    def execute(
        self,
        record: ServiceRestartRecord,
        *,
        restart_callable: Callable[[], bool],
        as_of: datetime | None = None,
    ) -> ServiceRestartRecord:
        now = as_of or datetime.now(timezone.utc)
        if not record.approved:
            return record
        try:
            succeeded = bool(restart_callable())
            return ServiceRestartRecord(
                **{
                    **record.__dict__,
                    "status": "COMPLETED" if succeeded else "FAILED",
                    "started_at": now.isoformat(),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "failure_message": (
                        None if succeeded else "RESTART_COMMAND_FAILED"
                    ),
                }
            )
        except BaseException as exc:
            return ServiceRestartRecord(
                **{
                    **record.__dict__,
                    "status": "FAILED",
                    "started_at": now.isoformat(),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "failure_message": f"{type(exc).__name__}:{exc}",
                }
            )
