from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from .order_profile import (
    CanonicalOrderAggregate,
    CanonicalOrderEvent,
    CanonicalOrderLeg,
)
from .order_repository_profile import OrderAuditEntry, OrderRepositoryRecord


def canonical_json(value: Any) -> str:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    else:
        try:
            value = asdict(value)
        except TypeError:
            pass
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def checksum(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def aggregate_from_dict(raw: dict[str, Any]) -> CanonicalOrderAggregate:
    payload = dict(raw)
    payload["legs"] = tuple(
        CanonicalOrderLeg(**leg) for leg in payload.get("legs", ())
    )
    return CanonicalOrderAggregate(**payload)


def event_from_dict(raw: dict[str, Any]) -> CanonicalOrderEvent:
    return CanonicalOrderEvent(**raw)


def record_from_dict(raw: dict[str, Any]) -> OrderRepositoryRecord:
    payload = dict(raw)
    payload["aggregate"] = aggregate_from_dict(payload["aggregate"])
    return OrderRepositoryRecord(**payload)


def audit_entry_from_dict(raw: dict[str, Any]) -> OrderAuditEntry:
    return OrderAuditEntry(**raw)
