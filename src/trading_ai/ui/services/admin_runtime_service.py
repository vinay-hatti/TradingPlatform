from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.models.admin_runtime import (
    AdminRuntimeResponse,
    ConfigurationDrift,
    EnvironmentProfile,
    FeatureFlag,
    ReadinessCheck,
    RuntimeComponent,
    RuntimeControlRequest,
    RuntimeControlResult,
    RuntimeSummary,
)


def val(row: Any, *names: str, default=None):
    for name in names:
        candidate = row.get(name) if isinstance(row, dict) else getattr(row, name, None)
        if candidate not in (None, ""):
            return candidate
    return default


def parse_dt(raw, fallback=None):
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if raw not in (None, ""):
        try:
            parsed = datetime.fromisoformat(
                str(raw).replace("Z", "+00:00")
            )
            return (
                parsed
                if parsed.tzinfo
                else parsed.replace(tzinfo=timezone.utc)
            )
        except ValueError:
            pass
    return fallback


class RuntimeCommandService(Protocol):
    def execute(
        self,
        action: str,
        target: str,
        reason: str,
    ) -> Any:
        ...


class AdminRuntimeService:
    PROFILE_PATTERNS = (
        "config/**/*environment*profile*.json",
        "config/**/*runtime*profile*.json",
        "config/**/*configuration*registry*.json",
        "runtime/**/*environment*profile*.json",
        "runtime/**/*profile*.json",
        "**/environment_profile*.json",
        "**/configuration_registry*.json",
    )
    HEALTH_PATTERNS = (
        "runtime/**/*health*.json",
        "runtime/**/*status*.json",
        "**/startup_readiness*.json",
        "**/runtime_health*.json",
    )
    FLAG_PATTERNS = (
        "config/**/*feature*.json",
        "runtime/**/*feature*.json",
        "**/feature_flags*.json",
    )
    DRIFT_PATTERNS = (
        "runtime/**/*drift*.json",
        "config/**/*drift*.json",
        "**/configuration_drift*.json",
    )

    PROFILE_FIELDS = {
        "environment",
        "environment_name",
        "profile",
        "profile_name",
        "active_profile",
        "profiles",
        "environments",
    }

    def __init__(
        self,
        artifacts=None,
        commands=None,
        stale_after_seconds=900,
    ):
        self.artifacts = artifacts or RepositoryArtifactAdapters()
        self.commands = commands
        self.stale_after_seconds = stale_after_seconds

    @property
    def root(self):
        return self.artifacts.root

    @property
    def reports_root(self):
        return self.root / "reports"

    def _files(self, patterns):
        found = {}
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
    def _time(path):
        return datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=timezone.utc,
        )

    @staticmethod
    def _read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    def _latest(self, patterns, validator=None):
        for path in self._files(patterns):
            try:
                payload = self._read(path)
            except Exception:
                continue
            if validator is None or validator(payload):
                return payload, path
        return {}, None

    @staticmethod
    def _rows(payload, *keys):
        if isinstance(payload, list):
            return [
                item
                for item in payload
                if isinstance(item, dict)
            ]
        if isinstance(payload, dict):
            for key in keys:
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    return [
                        item
                        for item in candidate
                        if isinstance(item, dict)
                    ]
            return [payload] if payload else []
        return []

    @classmethod
    def _is_profile_payload(cls, payload):
        if not isinstance(payload, (dict, list)):
            return False

        rows = cls._rows(
            payload,
            "profiles",
            "environments",
            "items",
        )
        if not rows:
            return False

        return any(
            bool(cls.PROFILE_FIELDS.intersection(row.keys()))
            for row in rows
        )

    def get(self):
        profile_payload, profile_path = self._latest(
            self.PROFILE_PATTERNS,
            validator=self._is_profile_payload,
        )
        health_payload, health_path = self._latest(
            self.HEALTH_PATTERNS
        )
        flag_payload, flag_path = self._latest(
            self.FLAG_PATTERNS
        )
        drift_payload, drift_path = self._latest(
            self.DRIFT_PATTERNS
        )

        profiles = []
        for index, row in enumerate(
            self._rows(
                profile_payload,
                "profiles",
                "environments",
                "items",
            )
        ):
            profiles.append(
                EnvironmentProfile(
                    environment=str(
                        val(
                            row,
                            "environment",
                            "environment_name",
                            "name",
                            default=os.getenv(
                                "TRADING_AI_ENV",
                                "UNKNOWN",
                            ),
                        )
                    ).upper(),
                    profile_name=str(
                        val(
                            row,
                            "profile_name",
                            "profile",
                            "active_profile",
                            default="DEFAULT",
                        )
                    ),
                    version=(
                        str(
                            val(
                                row,
                                "version",
                                "profile_version",
                                default="",
                            )
                        )
                        or None
                    ),
                    active=bool(
                        val(
                            row,
                            "active",
                            "is_active",
                            default=(index == 0),
                        )
                    ),
                    source=(
                        str(profile_path.relative_to(self.root))
                        if profile_path
                        else "environment"
                    ),
                    modified_at=(
                        self._time(profile_path)
                        if profile_path
                        else None
                    ),
                )
            )

        if not profiles:
            profiles = [
                EnvironmentProfile(
                    environment=os.getenv(
                        "TRADING_AI_ENV",
                        "UNKNOWN",
                    ).upper(),
                    profile_name=os.getenv(
                        "TRADING_AI_PROFILE",
                        "DEFAULT",
                    ),
                    active=True,
                    source="environment",
                )
            ]

        components = []
        readiness = []

        for row in self._rows(
            health_payload,
            "components",
            "services",
            "checks",
            "health",
            "items",
        ):
            status = str(
                val(
                    row,
                    "status",
                    "state",
                    "result",
                    default="UNKNOWN",
                )
            ).upper()

            component = RuntimeComponent(
                name=str(
                    val(
                        row,
                        "name",
                        "component",
                        "service",
                        "check",
                        default="runtime",
                    )
                ),
                status=status,
                detail=str(
                    val(
                        row,
                        "detail",
                        "message",
                        "description",
                        default="",
                    )
                ),
                last_checked_at=parse_dt(
                    val(
                        row,
                        "last_checked_at",
                        "checked_at",
                        "timestamp",
                    ),
                    (
                        self._time(health_path)
                        if health_path
                        else None
                    ),
                ),
                latency_ms=(
                    float(val(row, "latency_ms"))
                    if val(row, "latency_ms") not in (None, "")
                    else None
                ),
                source=(
                    str(health_path.relative_to(self.root))
                    if health_path
                    else ""
                ),
            )
            components.append(component)

            if bool(
                val(
                    row,
                    "readiness",
                    "required",
                    default=False,
                )
            ):
                readiness.append(
                    ReadinessCheck(
                        name=component.name,
                        status=status,
                        detail=component.detail,
                        required=bool(
                            val(
                                row,
                                "required",
                                default=True,
                            )
                        ),
                    )
                )

        if isinstance(health_payload, dict):
            for row in self._rows(
                health_payload.get("readiness", []),
                "checks",
                "items",
            ):
                readiness.append(
                    ReadinessCheck(
                        name=str(
                            val(
                                row,
                                "name",
                                "check",
                                default="readiness",
                            )
                        ),
                        status=str(
                            val(
                                row,
                                "status",
                                "result",
                                default="UNKNOWN",
                            )
                        ).upper(),
                        detail=str(
                            val(
                                row,
                                "detail",
                                "message",
                                default="",
                            )
                        ),
                        required=bool(
                            val(
                                row,
                                "required",
                                default=True,
                            )
                        ),
                    )
                )

        if (
            isinstance(flag_payload, dict)
            and flag_payload
            and all(
                isinstance(value, bool)
                for value in flag_payload.values()
            )
        ):
            flag_rows = [
                {"name": key, "enabled": value}
                for key, value in flag_payload.items()
            ]
        else:
            flag_rows = self._rows(
                flag_payload,
                "feature_flags",
                "flags",
                "items",
            )

        flags = [
            FeatureFlag(
                name=str(
                    val(
                        row,
                        "name",
                        "flag",
                        "key",
                    )
                ),
                enabled=bool(
                    val(
                        row,
                        "enabled",
                        "active",
                        "value",
                        default=False,
                    )
                ),
                scope=str(
                    val(
                        row,
                        "scope",
                        default="runtime",
                    )
                ),
                description=str(
                    val(
                        row,
                        "description",
                        "detail",
                        default="",
                    )
                ),
                source=(
                    str(flag_path.relative_to(self.root))
                    if flag_path
                    else ""
                ),
            )
            for row in flag_rows
            if val(row, "name", "flag", "key")
        ]

        drift = [
            ConfigurationDrift(
                key=str(
                    val(
                        row,
                        "key",
                        "name",
                        "setting",
                    )
                ),
                expected=(
                    str(
                        val(
                            row,
                            "expected",
                            "desired",
                            default="",
                        )
                    )
                    or None
                ),
                actual=(
                    str(
                        val(
                            row,
                            "actual",
                            "current",
                            default="",
                        )
                    )
                    or None
                ),
                status=str(
                    val(
                        row,
                        "status",
                        default="DRIFTED",
                    )
                ).upper(),
                source=(
                    str(drift_path.relative_to(self.root))
                    if drift_path
                    else ""
                ),
            )
            for row in self._rows(
                drift_payload,
                "drift",
                "differences",
                "items",
            )
            if val(row, "key", "name", "setting")
        ]

        healthy = sum(
            item.status
            in {"HEALTHY", "UP", "READY", "PASS", "OK"}
            for item in components
        )
        degraded = sum(
            item.status
            in {"DEGRADED", "WARNING", "WARN"}
            for item in components
        )
        failed = sum(
            item.status
            in {"FAILED", "DOWN", "ERROR", "CRITICAL"}
            for item in components
        )

        required_checks = [
            item
            for item in readiness
            if item.required
        ]

        if any(
            item.status
            in {"FAILED", "DOWN", "ERROR", "CRITICAL"}
            for item in required_checks
        ):
            readiness_status = "NOT_READY"
        elif any(
            item.status
            in {"DEGRADED", "WARNING", "WARN", "UNKNOWN"}
            for item in required_checks
        ):
            readiness_status = "DEGRADED"
        elif required_checks:
            readiness_status = "READY"
        elif failed:
            readiness_status = "NOT_READY"
        elif degraded:
            readiness_status = "DEGRADED"
        elif components:
            readiness_status = "READY"
        else:
            readiness_status = "UNKNOWN"

        drifted = [
            item
            for item in drift
            if item.status
            not in {"MATCH", "IN_SYNC", "OK", "PASS"}
        ]

        active = next(
            (
                item
                for item in profiles
                if item.active
            ),
            profiles[0],
        )

        paths = [
            path
            for path in (
                profile_path,
                health_path,
                flag_path,
                drift_path,
            )
            if path
        ]

        now = datetime.now(timezone.utc)
        latest = max(
            (self._time(path) for path in paths),
            default=None,
        )
        age = (
            max(
                0.0,
                (now - latest).total_seconds(),
            )
            if latest
            else None
        )

        notices = []
        if not components:
            notices.append(
                "No runtime health artifact was found."
            )
        if not readiness:
            notices.append(
                "No dedicated startup-readiness checks were found."
            )
        if not flags:
            notices.append(
                "No feature-flag artifact was found."
            )
        if self.commands is None:
            notices.append(
                "Runtime controls are read-only because no governed "
                "runtime command service is configured."
            )
        if drifted:
            notices.append(
                f"{len(drifted)} configuration drift items "
                "require review."
            )

        return AdminRuntimeResponse(
            generated_at=now,
            available=bool(
                profile_payload
                or health_payload
                or flag_payload
                or drift_payload
            ),
            stale=(
                age is None
                or age > self.stale_after_seconds
            ),
            age_seconds=(
                round(age, 2)
                if age is not None
                else None
            ),
            source_detail=(
                "; ".join(
                    str(path.relative_to(self.root))
                    for path in paths
                )
                or "Environment-derived defaults only."
            ),
            summary=RuntimeSummary(
                environment=active.environment,
                profile_name=active.profile_name,
                readiness_status=readiness_status,
                healthy_components=healthy,
                degraded_components=degraded,
                failed_components=failed,
                enabled_feature_flags=sum(
                    item.enabled for item in flags
                ),
                disabled_feature_flags=sum(
                    not item.enabled for item in flags
                ),
                configuration_drift_count=len(drifted),
                control_mode=(
                    "GOVERNED_WRITE"
                    if self.commands
                    else "READ_ONLY"
                ),
            ),
            profiles=profiles,
            components=components,
            feature_flags=flags,
            readiness=readiness,
            drift=drift,
            notices=notices,
        )

    def control(
        self,
        action,
        target,
        request: RuntimeControlRequest,
    ):
        now = datetime.now(timezone.utc)

        if self.commands is None:
            return RuntimeControlResult(
                accepted=False,
                action=action.upper(),
                target=target,
                message=(
                    "Runtime control center is read-only; governed "
                    "command service is not configured."
                ),
                requested_at=now,
            )

        result = self.commands.execute(
            action=action,
            target=target,
            reason=request.reason,
        )

        return RuntimeControlResult(
            accepted=True,
            action=action.upper(),
            target=target,
            message=str(result),
            requested_at=now,
        )
