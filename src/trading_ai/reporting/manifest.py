from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import UUID

from .context import REPORT_VERSION, ReportingContext


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_native(value: Any) -> Any:
    """Recursively convert report metadata into deterministic JSON-native values.

    Database result mappings commonly contain datetime/date, Decimal, UUID, Path,
    Enum, and occasionally numpy scalar values. Report manifests must never fail
    merely because one of those values appears in metadata.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (UUID, Path, Enum)):
        return str(value.value if isinstance(value, Enum) else value)
    if is_dataclass(value):
        return _json_native(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_native(item) for item in value]

    # Convert numpy/pandas scalar-like objects without importing those packages.
    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            converted = item_method()
        except (TypeError, ValueError):
            converted = value
        if converted is not value:
            return _json_native(converted)

    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return isoformat()
        except (TypeError, ValueError):
            pass
    return str(value)


def write_report_manifest(
    path: str | Path,
    *,
    context: ReportingContext,
    artifacts: Iterable[str | Path],
    report_type: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    artifact_rows = []
    for artifact in artifacts:
        artifact_path = Path(artifact)
        artifact_rows.append({
            "name": artifact_path.name,
            "path": str(artifact_path),
            "sha256": file_sha256(artifact_path) if artifact_path.exists() else None,
        })
    payload = {
        "report_version": REPORT_VERSION,
        "report_type": report_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reporting_context": _json_native(context.to_dict()),
        "artifacts": artifact_rows,
        "metadata": _json_native(dict(extra or {})),
    }
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target
