from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Any, Iterable

VOLATILE_FIELDS = {
    "generated_at", "created_at", "updated_at", "completed_at", "started_at",
    "decision_run_id", "decision_id", "scanner_run_id", "candidate_id", "rank",
    "report_manifest", "lineage_persistence",
}


def native(value: Any) -> Any:
    if is_dataclass(value):
        return native(asdict(value))
    if isinstance(value, dict):
        return {str(key): native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [native(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return native(value.value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):
        try:
            return native(value.item())
        except Exception:
            pass
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return native(vars(value))
    return value


def canonicalize(value: Any, *, strip_volatile: bool = True) -> Any:
    value = native(value)
    if isinstance(value, dict):
        return {
            key: canonicalize(item, strip_volatile=strip_volatile)
            for key, item in sorted(value.items())
            if not (strip_volatile and key in VOLATILE_FIELDS)
        }
    if isinstance(value, list):
        return [canonicalize(item, strip_volatile=strip_volatile) for item in value]
    return value


def canonical_json(value: Any, *, strip_volatile: bool = True) -> str:
    return json.dumps(canonicalize(value, strip_volatile=strip_volatile), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(value: Any, *, strip_volatile: bool = True) -> str:
    return sha256(canonical_json(value, strip_volatile=strip_volatile).encode("utf-8")).hexdigest()


def stable_key(item: dict[str, Any], category: str) -> str:
    if category == "candidate":
        return "|".join(str(item.get(name) or "") for name in ("symbol", "signal", "strategy", "expiry", "strike"))
    return "|".join(str(item.get(name) or "") for name in ("symbol", "strategy", "action", "recommendation"))


def index_items(items: Iterable[dict[str, Any]], category: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for position, item in enumerate(items, start=1):
        key = stable_key(item, category) or f"{category}:{position}"
        if key in indexed:
            key = f"{key}#{position}"
        indexed[key] = item
    return indexed
