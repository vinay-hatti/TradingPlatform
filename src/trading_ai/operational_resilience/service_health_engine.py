from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .service_health_policy import ServiceHealthPolicy
from .service_health_profile import (
    DependencyHealth,
    RuntimeHealthCheck,
    RuntimeHealthDecision,
    RuntimeHealthState,
    ServiceHeartbeat,
    ServiceHealthSnapshot,
)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class ServiceHealthEngine:
    def __init__(
        self,
        policy: ServiceHealthPolicy | None = None,
    ) -> None:
        self.policy = policy or ServiceHealthPolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def _dependency_status(
        self,
        dependency: DependencyHealth,
        *,
        as_of: datetime,
    ) -> tuple[bool, bool, str | None]:
        age = (
            as_of - _parse_timestamp(dependency.checked_at)
        ).total_seconds()
        normalized = dependency.status.strip().upper()
        stale = age > self.policy.dependency_stale_after_seconds
        failed = (
            normalized in {"DOWN", "FAILED", "UNAVAILABLE"}
            or dependency.consecutive_failures
            >= self.policy.maximum_consecutive_failures
        )
        degraded = normalized in {"DEGRADED", "WARN", "WARNING"} or stale

        if failed:
            return False, False, "FAILED"
        if degraded:
            return True, False, "DEGRADED"
        if normalized in {"UP", "READY", "HEALTHY", "AVAILABLE"}:
            return True, True, None
        if self.policy.reject_unknown_dependency_state:
            return False, False, "UNKNOWN"
        return True, False, "UNKNOWN"

    def snapshot_service(
        self,
        *,
        heartbeat: ServiceHeartbeat,
        dependencies: tuple[DependencyHealth, ...],
        as_of: datetime,
    ) -> ServiceHealthSnapshot:
        age = (
            as_of - _parse_timestamp(heartbeat.timestamp)
        ).total_seconds()
        normalized = heartbeat.status.strip().upper()
        dead = age > self.policy.heartbeat_dead_after_seconds
        stale = age > self.policy.heartbeat_stale_after_seconds

        failed_dependencies: list[str] = []
        degraded_dependencies: list[str] = []
        warnings: list[str] = []
        dependency_scores: list[float] = []

        for dependency in dependencies:
            ready, healthy, condition = self._dependency_status(
                dependency,
                as_of=as_of,
            )
            dependency_scores.append(
                100.0 if healthy else 70.0 if ready else 0.0
            )
            if condition == "FAILED":
                failed_dependencies.append(dependency.dependency_name)
            elif condition in {"DEGRADED", "UNKNOWN"}:
                degraded_dependencies.append(
                    dependency.dependency_name
                )
            if condition:
                warnings.append(
                    f"DEPENDENCY_{condition}:{dependency.dependency_name}"
                )

        heartbeat_ready = (
            not dead
            and normalized
            in {"UP", "READY", "HEALTHY", "RUNNING", "DEGRADED"}
        )
        heartbeat_healthy = (
            not stale
            and normalized in {"UP", "READY", "HEALTHY", "RUNNING"}
            and heartbeat.consecutive_failures
            < self.policy.maximum_consecutive_failures
        )
        if normalized not in {
            "UP",
            "READY",
            "HEALTHY",
            "RUNNING",
            "DEGRADED",
            "DOWN",
            "FAILED",
        } and self.policy.reject_unknown_service_state:
            heartbeat_ready = False
            heartbeat_healthy = False
            warnings.append("UNKNOWN_SERVICE_STATUS")

        critical_dependency_failure = any(
            dependency.critical
            and dependency.dependency_name in failed_dependencies
            for dependency in dependencies
        )
        too_many_degraded = (
            len(degraded_dependencies)
            > self.policy.maximum_degraded_dependencies
        )

        ready = (
            heartbeat_ready
            and not (
                self.policy.require_critical_dependencies
                and critical_dependency_failure
            )
        )
        healthy = (
            heartbeat_healthy
            and not failed_dependencies
            and not degraded_dependencies
            and not too_many_degraded
        )

        heartbeat_score = (
            100.0
            if heartbeat_healthy
            else 70.0
            if heartbeat_ready
            else 0.0
        )
        dependency_score = (
            sum(dependency_scores) / len(dependency_scores)
            if dependency_scores
            else 100.0
        )
        score = 0.6 * heartbeat_score + 0.4 * dependency_score

        status = (
            "HEALTHY"
            if healthy
            else "READY"
            if ready
            else "FAILED"
        )
        if ready and not healthy:
            status = "DEGRADED"

        if stale:
            warnings.append(
                f"STALE_HEARTBEAT:{heartbeat.service_name}"
            )
        if dead:
            warnings.append(
                f"DEAD_HEARTBEAT:{heartbeat.service_name}"
            )

        return ServiceHealthSnapshot(
            service_name=heartbeat.service_name,
            instance_id=heartbeat.instance_id,
            environment=heartbeat.environment,
            status=status,
            heartbeat_age_seconds=round(max(age, 0.0), 6),
            heartbeat_fresh=not stale,
            ready=ready,
            healthy=healthy,
            score=round(score, 2),
            critical=heartbeat.critical,
            dependencies=dependencies,
            degraded_dependencies=tuple(degraded_dependencies),
            failed_dependencies=tuple(failed_dependencies),
            warnings=tuple(dict.fromkeys(warnings)),
            metadata={
                "source_status": normalized,
                "heartbeat_sequence": heartbeat.sequence,
                "service_version": heartbeat.version,
            },
        )

    def evaluate(
        self,
        *,
        registry_id: str,
        environment: str,
        heartbeats: tuple[ServiceHeartbeat, ...],
        dependencies_by_service: dict[
            str,
            tuple[DependencyHealth, ...],
        ] | None = None,
        previous_state: RuntimeHealthState | None = None,
        as_of: datetime | None = None,
    ) -> RuntimeHealthDecision:
        now = as_of or datetime.now(timezone.utc)
        dependencies_by_service = dependencies_by_service or {}
        checks: list[RuntimeHealthCheck] = []

        def add(
            name: str,
            passed: bool,
            message: str,
            *,
            required: bool = True,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                RuntimeHealthCheck(
                    name=name,
                    passed=bool(passed),
                    required=required,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                    metadata=metadata or {},
                )
            )

        add(
            "heartbeats_present",
            bool(heartbeats),
            "At least one service heartbeat is required.",
        )
        identities = [
            (item.service_name, item.instance_id)
            for item in heartbeats
        ]
        add(
            "unique_service_instances",
            len(identities) == len(set(identities)),
            "Service instance identities are unique.",
        )
        add(
            "environment_consistency",
            all(
                item.environment == environment
                for item in heartbeats
            ),
            "All heartbeats belong to the requested environment.",
        )

        snapshots = tuple(
            self.snapshot_service(
                heartbeat=heartbeat,
                dependencies=dependencies_by_service.get(
                    heartbeat.service_name,
                    (),
                ),
                as_of=now,
            )
            for heartbeat in heartbeats
        )

        critical_failures = tuple(
            snapshot
            for snapshot in snapshots
            if snapshot.critical and not snapshot.ready
        )
        add(
            "critical_services_ready",
            not critical_failures
            or not self.policy.require_critical_services,
            "All critical services are ready.",
            required=self.policy.require_critical_services,
            metadata={
                "failed_services": tuple(
                    item.service_name for item in critical_failures
                )
            },
        )

        ready_count = sum(item.ready for item in snapshots)
        healthy_count = sum(item.healthy for item in snapshots)
        degraded_count = sum(
            item.status == "DEGRADED" for item in snapshots
        )
        failed_count = sum(
            item.status == "FAILED" for item in snapshots
        )
        service_score = (
            sum(item.score for item in snapshots) / len(snapshots)
            if snapshots
            else 0.0
        )

        required_checks = [check for check in checks if check.required]
        failed_checks = [
            check for check in required_checks if not check.passed
        ]
        check_score = (
            sum(check.score for check in required_checks)
            / len(required_checks)
            if required_checks
            else 100.0
        )
        score = (
            0.8 * service_score + 0.2 * check_score
            if snapshots
            else 0.0
        )
        ready = (
            not failed_checks
            and score >= self.policy.minimum_ready_score
            and ready_count == len(snapshots)
        )
        healthy = (
            ready
            and score >= self.policy.minimum_healthy_score
            and healthy_count == len(snapshots)
        )
        if not self.policy.fail_closed:
            ready = score >= self.policy.minimum_ready_score
            healthy = score >= self.policy.minimum_healthy_score

        overall_status = (
            "HEALTHY"
            if healthy
            else "READY"
            if ready
            else "DEGRADED"
            if ready_count > 0
            else "FAILED"
        )
        version = (
            previous_state.version + 1
            if previous_state is not None
            else 1
        )
        state = RuntimeHealthState(
            registry_id=registry_id,
            environment=environment,
            overall_status=overall_status,
            ready=ready,
            healthy=healthy,
            score=round(score, 2),
            service_count=len(snapshots),
            ready_service_count=ready_count,
            healthy_service_count=healthy_count,
            degraded_service_count=degraded_count,
            failed_service_count=failed_count,
            critical_failure_count=len(critical_failures),
            services=snapshots,
            version=version,
            updated_at=now.isoformat(),
            metadata={
                "previous_version": (
                    previous_state.version
                    if previous_state is not None
                    else None
                )
            },
        )

        grade, severity = self._grade(score)
        warnings = tuple(
            warning
            for snapshot in snapshots
            for warning in snapshot.warnings
        )
        rejection_reasons = tuple(
            check.name.upper()
            for check in failed_checks
        )
        return RuntimeHealthDecision(
            valid=True,
            allowed=ready,
            registry_id=registry_id,
            environment=environment,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation=(
                "READY"
                if healthy
                else "DEGRADED_READY"
                if ready
                else "NOT_READY"
            ),
            state=state,
            checks=tuple(checks),
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=rejection_reasons,
            metadata={
                "critical_failure_count": len(critical_failures),
                "failed_service_count": failed_count,
                "degraded_service_count": degraded_count,
            },
        )
