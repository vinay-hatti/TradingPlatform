from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BrokerErrorProfile:
    broker: str
    category: str
    code: str
    message: str
    retryable: bool = False
    fatal: bool = False
    http_status: int | None = None
    provider_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BrokerAdapterError(RuntimeError):
    def __init__(self, profile: BrokerErrorProfile) -> None:
        super().__init__(profile.message)
        self.profile = profile


def normalize_broker_error(
    broker: str,
    exc: Exception,
    *,
    category: str = "UNKNOWN",
    retryable: bool = False,
    fatal: bool = False,
) -> BrokerErrorProfile:
    return BrokerErrorProfile(
        broker=broker,
        category=category,
        code=exc.__class__.__name__.upper(),
        message=str(exc) or exc.__class__.__name__,
        retryable=retryable,
        fatal=fatal,
    )
