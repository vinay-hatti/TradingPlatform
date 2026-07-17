from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .slo_profile import RetentionResult
from .telemetry_retention_policy import (
    TelemetryRetentionPolicy,
    TelemetryRetentionRule,
)


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class TelemetryRetentionService:
    def __init__(
        self,
        policy: TelemetryRetentionPolicy | None = None,
    ) -> None:
        self.policy = policy or TelemetryRetentionPolicy()
        self.policy.validate()

    def enforce_records(
        self,
        *,
        records: list[dict[str, Any]],
        rule: TelemetryRetentionRule,
        timestamp_field: str,
        as_of: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], RetentionResult]:
        now = as_of or datetime.now(timezone.utc)
        retained = []
        archived = []
        deleted = 0

        ordered = sorted(
            records,
            key=lambda item: item.get(timestamp_field, ""),
            reverse=True,
        )
        for index, record in enumerate(ordered):
            timestamp = record.get(timestamp_field)
            expired = (
                timestamp is None
                or (now - _parse(timestamp)).total_seconds()
                > rule.retention_seconds
            )
            over_limit = (
                rule.maximum_records is not None
                and index >= rule.maximum_records
            )
            if expired or over_limit:
                if rule.archive_before_delete:
                    archived.append(record)
                deleted += 1
            else:
                retained.append(record)

        result = RetentionResult(
            telemetry_type=rule.telemetry_type,
            scanned=len(records),
            retained=len(retained),
            deleted=deleted,
            archived=len(archived),
            compliant=True,
            recommendation=(
                "RETENTION_ENFORCED"
                if deleted else "RETENTION_COMPLIANT"
            ),
        )
        return retained, archived, result

    def enforce_json_list(
        self,
        *,
        path: str | Path,
        list_key: str,
        rule: TelemetryRetentionRule,
        timestamp_field: str,
        archive_path: str | Path | None = None,
        as_of: datetime | None = None,
    ) -> RetentionResult:
        target = Path(path)
        if not target.exists():
            return RetentionResult(
                telemetry_type=rule.telemetry_type,
                scanned=0,
                retained=0,
                deleted=0,
                archived=0,
                compliant=True,
                recommendation="NO_DATA",
            )
        payload = json.loads(target.read_text(encoding="utf-8"))
        records = list(payload.get(list_key, []))
        retained, archived, result = self.enforce_records(
            records=records,
            rule=rule,
            timestamp_field=timestamp_field,
            as_of=as_of,
        )
        payload[list_key] = retained
        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if archived and archive_path is not None:
            archive = Path(archive_path)
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_text(
                json.dumps(
                    {list_key: archived},
                    indent=2,
                    sort_keys=True,
                ) + "\n",
                encoding="utf-8",
            )
        return result
