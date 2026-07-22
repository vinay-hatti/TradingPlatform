from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from trading_ai.scanner.universe_management.atomic_publisher import AtomicFilePublisher

from .models import ArtifactHealth, UniversePipelineResult


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_health(name: str, path: str | Path, expected_sha256: str = "") -> ArtifactHealth:
    target = Path(path)
    exists = target.is_file()
    digest = sha256_file(target) if exists else ""
    return ArtifactHealth(
        name=name,
        path=str(target),
        exists=exists,
        size_bytes=target.stat().st_size if exists else 0,
        sha256=digest,
        expected_sha256=expected_sha256,
        checksum_valid=bool(exists and (not expected_sha256 or digest == expected_sha256)),
    )


def write_json_atomic(path: str | Path, payload: Any) -> None:
    AtomicFilePublisher.publish_text(Path(path), json.dumps(payload, indent=2, default=str, sort_keys=True) + "\n")


def pipeline_html(result: UniversePipelineResult) -> str:
    stage_rows = "".join(
        f"<tr><td>{item.stage}</td><td>{item.status}</td><td>{item.elapsed_seconds:.3f}</td><td>{item.message}</td></tr>"
        for item in result.stage_results
    )
    artifact_rows = "".join(
        f"<tr><td>{item.name}</td><td>{item.exists}</td><td>{item.checksum_valid}</td><td>{item.size_bytes}</td><td><code>{item.sha256}</code></td></tr>"
        for item in result.artifacts
    )
    warnings = "".join(f"<li>{item}</li>" for item in result.warnings) or "<li>None</li>"
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>M35 Phase 1 Pipeline</title>
<style>body{{font-family:Arial,sans-serif;margin:2rem}}table{{border-collapse:collapse;width:100%;margin-bottom:2rem}}th,td{{border:1px solid #ccc;padding:.45rem;text-align:left}}code{{font-size:.75rem;word-break:break-all}}.READY{{color:#087f23}}.FAILED{{color:#b00020}}.DEGRADED{{color:#9a6700}}</style></head><body>
<h1>Institutional Market Universe Refresh</h1><h2 class='{result.status}'>Status: {result.status}</h2>
<p>Run ID: {result.run_id}<br>Elapsed: {result.elapsed_seconds:.3f}s<br>Universe: {result.universe_count}<br>Metrics: {result.metrics_count}<br>Eligible: {result.eligible_count}<br>Rejected: {result.rejected_count}<br>Review: {result.review_count}</p>
<h2>Stages</h2><table><tr><th>Stage</th><th>Status</th><th>Seconds</th><th>Message</th></tr>{stage_rows}</table>
<h2>Artifacts</h2><table><tr><th>Name</th><th>Exists</th><th>Checksum valid</th><th>Bytes</th><th>SHA-256</th></tr>{artifact_rows}</table>
<h2>Warnings</h2><ul>{warnings}</ul></body></html>"""
