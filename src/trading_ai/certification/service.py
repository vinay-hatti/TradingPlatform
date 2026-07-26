from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Iterable
from uuid import uuid4

from sqlalchemy import text

from trading_ai.reporting import ReportingContext, write_report_manifest

from .profile import CertificationCheck, CertificationPolicy, CertificationResult


def _run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"cert-{stamp}-{uuid4().hex[:10]}"


def _native(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_native(v) for v in value]
    return value


class Milestone47CertificationService:
    """End-to-end operational certification for Milestone 47.

    Checks are deliberately relational and artifact-based so certification proves
    the published-state lineage chain is present, queryable, and reproducible.
    """

    def __init__(self, session_factory: Callable[[], Any] | None = None, *, policy: CertificationPolicy | None = None) -> None:
        if session_factory is None:
            from trading_ai.database import SessionLocal
            session_factory = SessionLocal
        self.session_factory = session_factory
        self.policy = policy or CertificationPolicy()

    @staticmethod
    def _check(code: str, name: str, ok: bool, message: str, *, blocking: bool = True, severity: str = "ERROR", details: dict[str, Any] | None = None) -> CertificationCheck:
        return CertificationCheck(
            code=code,
            name=name,
            status="PASSED" if ok else "FAILED",
            severity="INFO" if ok else severity,
            message=message,
            blocking=blocking and not ok,
            details=dict(details or {}),
        )

    @staticmethod
    def _one(session: Any, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return session.execute(text(sql), params or {}).mappings().one_or_none()

    @staticmethod
    def _scalar(session: Any, sql: str, params: dict[str, Any] | None = None) -> Any:
        return session.execute(text(sql), params or {}).scalar_one_or_none()

    def run(self, *, report_manifest_paths: Iterable[str | Path] = ()) -> CertificationResult:
        started = datetime.now(timezone.utc)
        checks: list[CertificationCheck] = []
        metadata: dict[str, Any] = {}

        with self.session_factory() as session:
            head = self._scalar(session, "SELECT version_num FROM alembic_version LIMIT 1")
            checks.append(self._check(
                "MIGRATION_HEAD",
                "Alembic migration head",
                str(head or "") == self.policy.expected_alembic_head,
                f"Alembic head is {head!r}; expected {self.policy.expected_alembic_head!r}.",
                details={"actual": head, "expected": self.policy.expected_alembic_head},
            ))

            publication = self._one(session, """
                SELECT publication_name, run_id, readiness_status, scanner_ready,
                       decision_context_ready, option_snapshot_id, published_at,
                       as_of_date, market_intelligence_timestamp, option_snapshot_timestamp
                  FROM market_ingestion_publication
                 WHERE publication_name = :name
                 LIMIT 1
            """, {"name": self.policy.publication_name})
            pub_ok = publication is not None
            if publication and self.policy.require_ready_or_degraded_publication:
                pub_ok = str(publication.get("readiness_status") or "").upper() in {"READY", "DEGRADED"}
            checks.append(self._check(
                "PUBLICATION_AVAILABLE",
                "Published market state",
                pub_ok,
                "Authoritative publication exists and is usable." if pub_ok else "Authoritative publication is missing or unusable.",
                details=dict(publication or {}),
            ))

            scanner_ready = bool(publication and publication.get("scanner_ready"))
            checks.append(self._check(
                "SCANNER_READINESS",
                "Scanner readiness",
                scanner_ready or not self.policy.require_scanner_ready,
                "Publication is scanner-ready." if scanner_ready else "Publication is not scanner-ready.",
            ))
            decision_ready = bool(publication and publication.get("decision_context_ready"))
            checks.append(self._check(
                "DECISION_READINESS",
                "Decision readiness",
                decision_ready or not self.policy.require_decision_ready,
                "Publication is decision-context-ready." if decision_ready else "Publication is not decision-context-ready.",
            ))
            option_ok = bool(publication and publication.get("option_snapshot_id") and publication.get("option_snapshot_timestamp"))
            checks.append(self._check(
                "OPTION_SNAPSHOT_LINEAGE",
                "Option snapshot lineage",
                option_ok or not self.policy.require_option_snapshot,
                "Publication references an option snapshot ID and timestamp." if option_ok else "Option snapshot lineage is incomplete.",
                details={"option_snapshot_id": publication.get("option_snapshot_id") if publication else None},
            ))

            scanner = self._one(session, """
                SELECT scanner_run_id, publication_name, ingestion_run_id, publication_status,
                       option_snapshot_id, market_state_hash, scanner_version,
                       candidate_count, status, completed_at
                  FROM scanner_lineage_run
                 ORDER BY completed_at DESC NULLS LAST, started_at DESC
                 LIMIT 1
            """)
            scanner_ok = scanner is not None and str(scanner.get("status") or "").upper() == "READY"
            checks.append(self._check(
                "SCANNER_LINEAGE",
                "Scanner-run lineage",
                scanner_ok or not self.policy.require_scanner_lineage,
                "Latest scanner lineage run is READY." if scanner_ok else "No READY scanner lineage run was found.",
                details=dict(scanner or {}),
            ))

            candidate_count = 0
            candidate_consistent = False
            if scanner:
                candidate_count = int(self._scalar(session, """
                    SELECT COUNT(*) FROM scanner_candidate_lineage
                     WHERE scanner_run_id = :scanner_run_id
                """, {"scanner_run_id": scanner["scanner_run_id"]}) or 0)
                candidate_consistent = candidate_count == int(scanner.get("candidate_count") or 0)
            checks.append(self._check(
                "CANDIDATE_LINEAGE",
                "Candidate lineage consistency",
                candidate_consistent or not self.policy.require_candidate_lineage,
                f"Persisted candidate rows={candidate_count}; scanner-run candidate_count={scanner.get('candidate_count') if scanner else None}.",
                details={"persisted_count": candidate_count, "declared_count": scanner.get("candidate_count") if scanner else None},
            ))

            decision = self._one(session, """
                SELECT decision_run_id, publication_name, ingestion_run_id, publication_status,
                       option_snapshot_id, market_state_hash, decision_engine_version,
                       policy_version, decision_count, status, completed_at
                  FROM institutional_decision_lineage_run
                 ORDER BY completed_at DESC NULLS LAST, started_at DESC
                 LIMIT 1
            """)
            decision_ok = decision is not None and str(decision.get("status") or "").upper() == "READY"
            checks.append(self._check(
                "DECISION_LINEAGE",
                "Institutional-decision lineage",
                decision_ok or not self.policy.require_decision_lineage,
                "Latest decision lineage run is READY." if decision_ok else "No READY decision lineage run was found; optional under current policy.",
                blocking=self.policy.require_decision_lineage,
                severity="WARNING" if not self.policy.require_decision_lineage else "ERROR",
                details=dict(decision or {}),
            ))

            replay = self._one(session, """
                SELECT replay_run_id, source_scanner_run_id, source_decision_run_id,
                       replay_mode, status, mismatch_count, completed_at
                  FROM historical_replay_run
                 ORDER BY completed_at DESC NULLS LAST, started_at DESC
                 LIMIT 1
            """)
            replay_exists = replay is not None
            replay_clean = replay_exists and str(replay.get("status") or "").upper() == "READY" and int(replay.get("mismatch_count") or 0) == 0
            replay_required = self.policy.require_replay_history
            replay_ok = replay_clean if (replay_required or replay_exists) else True
            checks.append(self._check(
                "HISTORICAL_REPLAY",
                "Historical replay determinism",
                replay_ok,
                "Latest replay is READY with zero mismatches." if replay_clean else ("No replay history exists; optional under current policy." if not replay_exists and not replay_required else "Latest replay is missing, failed, or contains mismatches."),
                blocking=replay_required or (replay_exists and self.policy.require_zero_latest_replay_mismatches),
                severity="WARNING" if not replay_required and not replay_exists else "ERROR",
                details=dict(replay or {}),
            ))

            metadata.update({
                "publication": dict(publication or {}),
                "latest_scanner_run": dict(scanner or {}),
                "latest_decision_run": dict(decision or {}),
                "latest_replay_run": dict(replay or {}),
            })

        manifest_paths = [Path(path) for path in report_manifest_paths]
        manifest_errors: list[str] = []
        checked_artifacts = 0
        for manifest_path in manifest_paths:
            if not manifest_path.exists():
                manifest_errors.append(f"Missing manifest: {manifest_path}")
                continue
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                for artifact in payload.get("artifacts", []):
                    artifact_path = Path(artifact.get("path") or manifest_path.parent / str(artifact.get("name")))
                    if not artifact_path.is_absolute():
                        artifact_path = manifest_path.parent / artifact_path.name
                    if not artifact_path.exists():
                        manifest_errors.append(f"Missing artifact: {artifact_path}")
                        continue
                    actual = sha256(artifact_path.read_bytes()).hexdigest()
                    expected = artifact.get("sha256")
                    checked_artifacts += 1
                    if expected and actual != expected:
                        manifest_errors.append(f"Checksum mismatch: {artifact_path}")
            except Exception as exc:
                manifest_errors.append(f"Invalid manifest {manifest_path}: {exc}")
        manifests_ok = not manifest_errors
        if not manifest_paths and self.policy.require_manifest_integrity:
            manifests_ok = False
            manifest_errors.append("No report manifests were supplied for integrity validation.")
        checks.append(self._check(
            "REPORT_MANIFEST_INTEGRITY",
            "Report manifest integrity",
            manifests_ok or not self.policy.require_manifest_integrity,
            f"Validated {len(manifest_paths)} manifest(s) and {checked_artifacts} artifact(s)." if manifests_ok else "; ".join(manifest_errors),
            blocking=self.policy.require_manifest_integrity,
            details={"manifest_count": len(manifest_paths), "artifact_count": checked_artifacts, "errors": manifest_errors},
        ))

        completed = datetime.now(timezone.utc)
        blocking_failures = [item for item in checks if item.blocking and item.status == "FAILED"]
        status = "CERTIFIED" if not blocking_failures else "FAILED"
        metadata.update({
            "check_count": len(checks),
            "passed_count": sum(item.status == "PASSED" for item in checks),
            "failed_count": sum(item.status == "FAILED" for item in checks),
            "blocking_failure_count": len(blocking_failures),
        })
        return CertificationResult(
            certification_run_id=_run_id(),
            status=status,
            started_at=started,
            completed_at=completed,
            checks=tuple(checks),
            metadata=metadata,
        )

    def export(self, result: CertificationResult, output_dir: str | Path) -> dict[str, Path]:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        json_path = target / "milestone47_certification.json"
        payload = _native(asdict(result))
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

        rows = []
        for check in result.checks:
            rows.append(
                "<tr>"
                f"<td>{check.code}</td><td>{check.name}</td><td>{check.status}</td>"
                f"<td>{check.severity}</td><td>{check.message}</td>"
                "</tr>"
            )
        html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Milestone 47 Certification</title>
<style>body{{font-family:Arial,sans-serif;margin:32px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:8px;text-align:left}}th{{background:#f2f2f2}}.status{{font-size:24px;font-weight:bold}}</style></head>
<body><h1>Milestone 47 End-to-End Certification</h1>
<p class='status'>Status: {result.status}</p>
<p>Certification Run: {result.certification_run_id}</p>
<p>Started: {result.started_at.isoformat()}<br>Completed: {result.completed_at.isoformat()}</p>
<h2>Certification Checks</h2><table><thead><tr><th>Code</th><th>Check</th><th>Status</th><th>Severity</th><th>Message</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Summary</h2><pre>{json.dumps(_native(result.metadata), indent=2, sort_keys=True, default=str)}</pre>
</body></html>"""
        html_path = target / "milestone47_certification.html"
        html_path.write_text(html, encoding="utf-8")

        publication = result.metadata.get("publication") or {}
        scanner = result.metadata.get("latest_scanner_run") or {}
        decision = result.metadata.get("latest_decision_run") or {}
        context = ReportingContext(
            report_version=self.policy.report_version,
            publication_name=publication.get("publication_name"),
            publication_status=str(publication.get("readiness_status") or "UNKNOWN"),
            published_at=str(publication.get("published_at")) if publication.get("published_at") else None,
            ingestion_run_id=publication.get("run_id"),
            scanner_run_id=scanner.get("scanner_run_id"),
            decision_run_id=decision.get("decision_run_id"),
            market_as_of_date=str(publication.get("as_of_date")) if publication.get("as_of_date") else None,
            option_snapshot_id=publication.get("option_snapshot_id"),
            option_snapshot_timestamp=str(publication.get("option_snapshot_timestamp")) if publication.get("option_snapshot_timestamp") else None,
            market_intelligence_snapshot_timestamp=str(publication.get("market_intelligence_timestamp")) if publication.get("market_intelligence_timestamp") else None,
            scanner_ready=publication.get("scanner_ready"),
            decision_context_ready=publication.get("decision_context_ready"),
            published_state_degraded=str(publication.get("readiness_status") or "").upper() == "DEGRADED",
            market_state_hash=scanner.get("market_state_hash") or decision.get("market_state_hash"),
            scanner_version=scanner.get("scanner_version"),
            decision_engine_version=decision.get("decision_engine_version"),
            policy_version=decision.get("policy_version"),
        )
        manifest_path = write_report_manifest(
            target / "milestone47_certification_manifest.json",
            context=context,
            artifacts=[json_path, html_path],
            report_type="milestone47_end_to_end_certification",
            extra={"certification_run_id": result.certification_run_id, "status": result.status, **result.metadata},
        )
        return {"json": json_path, "html": html_path, "manifest": manifest_path}
