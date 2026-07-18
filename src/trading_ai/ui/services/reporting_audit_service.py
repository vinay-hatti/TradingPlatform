from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.models.reporting_audit import (
    AuditEvent,
    GovernanceEvidence,
    ReportArtifact,
    ReportingAuditResponse,
    ReportingAuditSummary,
)


def val(row: Any, *names: str, default=None):
    for name in names:
        candidate = row.get(name) if isinstance(row, dict) else getattr(row, name, None)
        if candidate not in (None, ""):
            return candidate
    return default


def parse_datetime(raw: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if raw not in (None, ""):
        text = str(raw).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return fallback or datetime.now(timezone.utc)


class ReportingAuditService:
    REPORT_EXTENSIONS = {
        ".html",
        ".json",
        ".csv",
        ".md",
        ".txt",
        ".pdf",
    }
    AUDIT_PATTERNS = (
        "audit/**/*.json",
        "audit/**/*.csv",
        "governance/**/*audit*.json",
        "governance/**/*audit*.csv",
        "**/audit_log*.json",
        "**/audit_log*.csv",
        "**/decision_trace*.json",
        "**/decision_trace*.csv",
        "**/governance_events*.json",
        "**/governance_events*.csv",
    )
    HASH_MANIFEST_PATTERNS = (
        "**/manifest*.json",
        "**/checksums*.json",
        "**/integrity*.json",
    )

    def __init__(
        self,
        artifacts: RepositoryArtifactAdapters | None = None,
        stale_after_seconds: int = 7 * 24 * 3600,
        max_reports: int = 250,
        max_audit_events: int = 500,
    ):
        self.artifacts = artifacts or RepositoryArtifactAdapters()
        self.stale_after_seconds = stale_after_seconds
        self.max_reports = max_reports
        self.max_audit_events = max_audit_events

    @property
    def root(self) -> Path:
        return self.artifacts.root

    @property
    def reports_root(self) -> Path:
        return self.root / "reports"

    @staticmethod
    def _file_time(path: Path) -> datetime:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _category(self, path: Path) -> str:
        relative = path.relative_to(self.reports_root)
        first = relative.parts[0].lower() if relative.parts else "general"
        name = path.name.lower()
        if "execution" in name or "broker" in name:
            return "Execution"
        if "risk" in name or "drawdown" in name or "tail" in name:
            return "Risk"
        if "portfolio" in name or "position" in name:
            return "Portfolio"
        if "walk_forward" in name or "governance" in name:
            return "Governance"
        if "scanner" in name or "opportunit" in name:
            return "Opportunity"
        if "backtest" in name or "experiment" in name:
            return "Research"
        return first.replace("_", " ").title()

    def _description(self, path: Path, category: str) -> str:
        stem = path.stem.replace("_", " ").replace("-", " ").strip().title()
        return f"{category} artifact: {stem}"

    def _load_manifests(self) -> dict[str, str]:
        expected: dict[str, str] = {}
        for pattern in self.HASH_MANIFEST_PATTERNS:
            for path in self.reports_root.glob(pattern):
                if not path.is_file():
                    continue
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if isinstance(payload, dict):
                    for key, value in payload.items():
                        if isinstance(value, str) and len(value) == 64:
                            expected[str(key)] = value.lower()
                        elif isinstance(value, dict):
                            candidate = val(value, "sha256", "checksum", "hash")
                            if isinstance(candidate, str) and len(candidate) == 64:
                                expected[str(key)] = candidate.lower()
        return expected

    def _reports(self) -> list[ReportArtifact]:
        now = datetime.now(timezone.utc)
        manifests = self._load_manifests()
        paths = [
            path
            for path in self.reports_root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in self.REPORT_EXTENSIONS
            and "audit" not in path.parts
        ]
        paths.sort(key=lambda item: item.stat().st_mtime, reverse=True)

        reports: list[ReportArtifact] = []
        for path in paths[: self.max_reports]:
            modified = self._file_time(path)
            age = max(0.0, (now - modified).total_seconds())
            relative = str(path.relative_to(self.root))
            category = self._category(path)
            expected = (
                manifests.get(relative)
                or manifests.get(str(path.relative_to(self.reports_root)))
                or manifests.get(path.name)
            )

            actual = None
            status = "NOT_VERIFIED"
            if expected:
                try:
                    actual = self._sha256(path)
                    status = "VERIFIED" if actual.lower() == expected.lower() else "FAILED"
                except OSError:
                    status = "FAILED"

            reports.append(
                ReportArtifact(
                    name=path.name,
                    category=category,
                    relative_path=relative,
                    extension=path.suffix.lower().lstrip("."),
                    size_bytes=path.stat().st_size,
                    modified_at=modified,
                    age_seconds=round(age, 2),
                    stale=age > self.stale_after_seconds,
                    sha256=actual,
                    integrity_status=status,
                    description=self._description(path, category),
                )
            )
        return reports

    @staticmethod
    def _read_rows(path: Path) -> list[dict[str, Any]]:
        if path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict)]
            if isinstance(payload, dict):
                for key in ("events", "audit_events", "records", "items", "data"):
                    candidate = payload.get(key)
                    if isinstance(candidate, list):
                        return [item for item in candidate if isinstance(item, dict)]
                return [payload]
            return []
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def _audit_events(self) -> list[AuditEvent]:
        paths: dict[str, Path] = {}
        for pattern in self.AUDIT_PATTERNS:
            for path in self.reports_root.glob(pattern):
                if path.is_file():
                    paths[str(path.resolve())] = path

        events: list[AuditEvent] = []
        for path in sorted(
            paths.values(),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        ):
            fallback = self._file_time(path)
            try:
                rows = self._read_rows(path)
            except Exception:
                continue

            for index, row in enumerate(rows):
                occurred = parse_datetime(
                    val(
                        row,
                        "occurred_at",
                        "timestamp",
                        "created_at",
                        "event_time",
                        "time",
                    ),
                    fallback=fallback,
                )
                event_type = str(
                    val(
                        row,
                        "event_type",
                        "type",
                        "category",
                        default="AUDIT_EVENT",
                    )
                ).upper()
                severity = str(
                    val(
                        row,
                        "severity",
                        "level",
                        default="INFO",
                    )
                ).upper()
                action = str(
                    val(
                        row,
                        "action",
                        "operation",
                        "event",
                        default=event_type,
                    )
                )
                outcome = str(
                    val(
                        row,
                        "outcome",
                        "status",
                        "result",
                        default="UNKNOWN",
                    )
                ).upper()
                event_id = str(
                    val(
                        row,
                        "event_id",
                        "audit_id",
                        "id",
                        default=f"{path.stem}-{index}",
                    )
                )
                events.append(
                    AuditEvent(
                        event_id=event_id,
                        occurred_at=occurred,
                        event_type=event_type,
                        severity=severity,
                        actor=str(
                            val(
                                row,
                                "actor",
                                "user",
                                "principal",
                                "service",
                                default="system",
                            )
                        ),
                        entity_type=str(
                            val(
                                row,
                                "entity_type",
                                "resource_type",
                                default="platform",
                            )
                        ),
                        entity_id=(
                            str(
                                val(
                                    row,
                                    "entity_id",
                                    "resource_id",
                                    "order_id",
                                    "decision_id",
                                    default="",
                                )
                            )
                            or None
                        ),
                        action=action,
                        outcome=outcome,
                        message=str(
                            val(
                                row,
                                "message",
                                "detail",
                                "description",
                                "reason",
                                default="",
                            )
                        ),
                        source=str(path.relative_to(self.root)),
                    )
                )

        events.sort(key=lambda item: item.occurred_at, reverse=True)
        return events[: self.max_audit_events]

    def _governance(
        self,
        reports: list[ReportArtifact],
        events: list[AuditEvent],
    ) -> list[GovernanceEvidence]:
        def latest_for(predicate):
            timestamps = [
                event.occurred_at
                for event in events
                if predicate(event)
            ]
            return max(timestamps) if timestamps else None

        integrity_failed = sum(
            1 for report in reports if report.integrity_status == "FAILED"
        )
        integrity_verified = sum(
            1 for report in reports if report.integrity_status == "VERIFIED"
        )
        rejection_events = [
            event
            for event in events
            if event.outcome in {"REJECTED", "FAILED", "DENIED"}
        ]
        governance_reports = [
            report
            for report in reports
            if report.category == "Governance"
        ]
        execution_reports = [
            report
            for report in reports
            if report.category == "Execution"
        ]

        return [
            GovernanceEvidence(
                control="Artifact integrity",
                status=(
                    "FAIL"
                    if integrity_failed
                    else "PASS"
                    if integrity_verified
                    else "WARNING"
                ),
                evidence_count=integrity_verified + integrity_failed,
                latest_evidence_at=max(
                    (
                        report.modified_at
                        for report in reports
                        if report.integrity_status in {"VERIFIED", "FAILED"}
                    ),
                    default=None,
                ),
                detail=(
                    f"{integrity_verified} verified; "
                    f"{integrity_failed} failed."
                ),
            ),
            GovernanceEvidence(
                control="Decision and operational audit trail",
                status="PASS" if events else "WARNING",
                evidence_count=len(events),
                latest_evidence_at=events[0].occurred_at if events else None,
                detail="Audit events captured from repository-native artifacts.",
            ),
            GovernanceEvidence(
                control="Rejected or failed action review",
                status="WARNING" if rejection_events else "PASS",
                evidence_count=len(rejection_events),
                latest_evidence_at=max(
                    (event.occurred_at for event in rejection_events),
                    default=None,
                ),
                detail=(
                    "Rejected, denied, or failed actions requiring review."
                ),
            ),
            GovernanceEvidence(
                control="Walk-forward and parameter governance evidence",
                status="PASS" if governance_reports else "WARNING",
                evidence_count=len(governance_reports),
                latest_evidence_at=max(
                    (report.modified_at for report in governance_reports),
                    default=None,
                ),
                detail="Governance and walk-forward reports available.",
            ),
            GovernanceEvidence(
                control="Execution reporting evidence",
                status="PASS" if execution_reports else "WARNING",
                evidence_count=len(execution_reports),
                latest_evidence_at=max(
                    (report.modified_at for report in execution_reports),
                    default=None,
                ),
                detail="Execution and broker operational reports available.",
            ),
        ]

    def get(self) -> ReportingAuditResponse:
        reports = self._reports()
        events = self._audit_events()
        governance = self._governance(reports, events)

        summary = ReportingAuditSummary(
            report_count=len(reports),
            audit_event_count=len(events),
            critical_event_count=sum(
                1 for event in events if event.severity == "CRITICAL"
            ),
            warning_event_count=sum(
                1 for event in events if event.severity == "WARNING"
            ),
            stale_report_count=sum(1 for report in reports if report.stale),
            verified_report_count=sum(
                1
                for report in reports
                if report.integrity_status == "VERIFIED"
            ),
            failed_integrity_count=sum(
                1
                for report in reports
                if report.integrity_status == "FAILED"
            ),
            governance_pass_count=sum(
                1 for item in governance if item.status == "PASS"
            ),
            governance_warning_count=sum(
                1 for item in governance if item.status == "WARNING"
            ),
            governance_fail_count=sum(
                1 for item in governance if item.status == "FAIL"
            ),
        )

        notices = []
        if not reports:
            notices.append("No report artifacts were found.")
        if not events:
            notices.append("No repository-native audit events were found.")
        if summary.failed_integrity_count:
            notices.append(
                f"{summary.failed_integrity_count} report artifacts failed integrity verification."
            )
        if summary.stale_report_count:
            notices.append(
                f"{summary.stale_report_count} report artifacts exceed the freshness threshold."
            )

        return ReportingAuditResponse(
            generated_at=datetime.now(timezone.utc),
            available=bool(reports or events),
            source_detail=str(self.reports_root),
            summary=summary,
            reports=reports,
            audit_events=events,
            governance=governance,
            notices=notices,
        )
