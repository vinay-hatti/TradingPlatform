from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "event_type",
            "component",
            "operation",
            "outcome",
            "duration_ms",
            "correlation_id",
            "resource_id",
            "environment",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True, default=str)


class StructuredLogManager:
    def __init__(
        self,
        path: Path | str = "reports/observability/workstation.jsonl",
        logger_name: str = "trading_ai.workstation",
    ):
        self.path = Path(path)
        self.logger_name = logger_name
        self._lock = RLock()
        self._logger: logging.Logger | None = None

    def logger(self) -> logging.Logger:
        with self._lock:
            if self._logger is not None:
                return self._logger
            self.path.parent.mkdir(parents=True, exist_ok=True)
            logger = logging.getLogger(self.logger_name)
            logger.setLevel(logging.INFO)
            logger.propagate = False

            expected = str(self.path.resolve())
            already_configured = any(
                isinstance(handler, logging.FileHandler)
                and handler.baseFilename == expected
                for handler in logger.handlers
            )
            if not already_configured:
                handler = logging.FileHandler(
                    self.path,
                    encoding="utf-8",
                )
                handler.setFormatter(JsonLineFormatter())
                logger.addHandler(handler)
            self._logger = logger
            return logger

    def emit(
        self,
        *,
        level: int = logging.INFO,
        message: str,
        **fields: Any,
    ) -> None:
        self.logger().log(level, message, extra=fields)
