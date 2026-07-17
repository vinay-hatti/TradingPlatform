from __future__ import annotations

import json
from typing import Any

from .observability_policy import StructuredLoggingPolicy
from .observability_profile import (
    ObservabilityContext,
    StructuredLogRecord,
)


_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


class StructuredLoggingService:
    def __init__(
        self,
        policy: StructuredLoggingPolicy | None = None,
    ) -> None:
        self.policy = policy or StructuredLoggingPolicy()
        self.policy.validate()

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if (
                    self.policy.redact_sensitive_fields
                    and key.lower() in self.policy.sensitive_field_names
                ):
                    result[key] = "[REDACTED]"
                else:
                    result[key] = self._redact(item)
            return result
        if isinstance(value, (list, tuple)):
            return [self._redact(item) for item in value]
        return value

    def should_emit(self, level: str) -> bool:
        normalized = level.upper()
        if normalized not in _LEVELS:
            raise ValueError(f"Unsupported log level: {level}")
        return _LEVELS[normalized] >= _LEVELS[
            self.policy.minimum_level.upper()
        ]

    def create_record(
        self,
        *,
        level: str,
        message: str,
        context: ObservabilityContext,
        event_name: str | None = None,
        exception: BaseException | None = None,
        fields: dict[str, Any] | None = None,
    ) -> StructuredLogRecord | None:
        normalized = level.upper()
        if not self.should_emit(normalized):
            return None
        truncated = message[: self.policy.maximum_message_length]
        return StructuredLogRecord(
            level=normalized,
            message=truncated,
            context=context,
            event_name=event_name,
            exception_type=(
                type(exception).__name__ if exception else None
            ),
            exception_message=str(exception) if exception else None,
            fields=self._redact(fields or {}),
        )

    def serialize(self, record: StructuredLogRecord) -> str:
        try:
            payload = record.to_dict()
            payload["fields"] = self._redact(payload.get("fields", {}))
            payload["context"]["metadata"] = self._redact(
                payload["context"].get("metadata", {})
            )
            return json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        except BaseException:
            if self.policy.fail_closed_on_serialization_error:
                raise
            return json.dumps({
                "level": "ERROR",
                "message": "LOG_SERIALIZATION_FAILED",
            })
