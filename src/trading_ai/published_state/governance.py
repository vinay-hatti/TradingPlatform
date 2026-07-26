from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class PublishedStateConsumer(str, Enum):
    GENERIC = "generic"
    SCANNER = "scanner"
    DECISION = "decision"


class PublishedStateFailureCode(str, Enum):
    PUBLICATION_MISSING = "PUBLICATION_MISSING"
    STATUS_NOT_READY = "STATUS_NOT_READY"
    DEGRADED_NOT_ALLOWED = "DEGRADED_NOT_ALLOWED"
    PUBLICATION_STALE = "PUBLICATION_STALE"
    SCANNER_NOT_READY = "SCANNER_NOT_READY"
    DECISION_CONTEXT_NOT_READY = "DECISION_CONTEXT_NOT_READY"
    OPTION_SNAPSHOT_MISSING = "OPTION_SNAPSHOT_MISSING"
    MARKET_INTELLIGENCE_TIMESTAMP_MISSING = "MARKET_INTELLIGENCE_TIMESTAMP_MISSING"
    OPTION_SNAPSHOT_TIMESTAMP_MISSING = "OPTION_SNAPSHOT_TIMESTAMP_MISSING"
    INVALID_PUBLICATION_RECORD = "INVALID_PUBLICATION_RECORD"


class PublishedStateSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class PublishedStateFinding:
    code: str
    severity: str
    message: str
    blocking: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "blocking": self.blocking,
        }


def blocking_findings(findings: Iterable[PublishedStateFinding]) -> tuple[PublishedStateFinding, ...]:
    return tuple(item for item in findings if item.blocking)
