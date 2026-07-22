from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import csv
import hashlib
import html
import io
import json
from pathlib import Path

from .atomic_publisher import AtomicFilePublisher
from .builder_profile import UniverseRefreshResult
from .reconciliation import ReconciliationResult
from .universe_profile import UniverseBuildResult


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def canonical_csv_text(build: UniverseBuildResult) -> str:
    buffer = io.StringIO(newline="")
    fieldnames = [
        "symbol", "name", "exchange", "asset_type", "active", "tradable",
        "options_eligible", "sector", "industry", "market_cap",
        "average_daily_volume", "source",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for item in build.universe.securities:
        writer.writerow({name: getattr(item, name) for name in fieldnames})
    return buffer.getvalue()


def sha256_text(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def manifest_payload(*, build: UniverseBuildResult, reconciliation: ReconciliationResult, refresh: UniverseRefreshResult, csv_sha256: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "universe_id": build.universe.universe_id,
        "generated_at": refresh.generated_at.isoformat(),
        "governance_status": refresh.status,
        "published": refresh.published,
        "symbol_count": refresh.symbol_count,
        "csv_sha256": csv_sha256,
        "providers": [
            {
                "name": result.provider_name,
                "success": result.success,
                "from_cache": result.from_cache,
                "fetched_at": result.fetched_at.isoformat(),
                "security_count": len(result.securities),
                "source_uri": result.source_uri,
                "warning": result.warning,
                "error_type": result.error_type,
                "metadata": result.metadata,
            }
            for result in reconciliation.provider_results
        ],
        "counts": {
            "received": build.received_count,
            "accepted": build.accepted_count,
            "rejected": build.rejected_count,
            "duplicates": build.duplicate_count,
            "added": refresh.added_count,
            "removed": refresh.removed_count,
            "unchanged": refresh.unchanged_count,
        },
        "warnings": list(refresh.warnings),
        "artifacts": refresh.artifacts,
    }


def summary_payload(refresh: UniverseRefreshResult, build: UniverseBuildResult) -> dict[str, object]:
    return {
        "generated_at": refresh.generated_at.isoformat(),
        "status": refresh.status,
        "published": refresh.published,
        "symbol_count": refresh.symbol_count,
        "added_count": refresh.added_count,
        "removed_count": refresh.removed_count,
        "unchanged_count": refresh.unchanged_count,
        "failed_provider_count": refresh.failed_provider_count,
        "stale_provider_count": refresh.stale_provider_count,
        "source_names": list(refresh.source_names),
        "warnings": list(refresh.warnings),
        "rejection_reasons": build.rejection_reasons,
        "artifacts": refresh.artifacts,
    }


def refresh_report_html(refresh: UniverseRefreshResult) -> str:
    warnings = "".join(f"<li>{html.escape(item)}</li>" for item in refresh.warnings) or "<li>None</li>"
    artifacts = "".join(f"<li><strong>{html.escape(key)}</strong>: {html.escape(value)}</li>" for key, value in refresh.artifacts.items())
    return f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><title>Universe Refresh Report</title></head>
<body><h1>Automatic Universe Refresh</h1>
<table border=\"1\" cellpadding=\"6\"><tr><th>Status</th><td>{html.escape(refresh.status)}</td></tr>
<tr><th>Published</th><td>{refresh.published}</td></tr><tr><th>Symbols</th><td>{refresh.symbol_count}</td></tr>
<tr><th>Added</th><td>{refresh.added_count}</td></tr><tr><th>Removed</th><td>{refresh.removed_count}</td></tr>
<tr><th>Unchanged</th><td>{refresh.unchanged_count}</td></tr><tr><th>Failed providers</th><td>{refresh.failed_provider_count}</td></tr>
<tr><th>Stale providers</th><td>{refresh.stale_provider_count}</td></tr><tr><th>Generated</th><td>{refresh.generated_at.isoformat()}</td></tr></table>
<h2>Warnings</h2><ul>{warnings}</ul><h2>Artifacts</h2><ul>{artifacts}</ul></body></html>\n"""


def write_json_atomic(path: Path, payload: object) -> Path:
    return AtomicFilePublisher.publish_text(path, json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n")
