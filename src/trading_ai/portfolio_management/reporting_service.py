from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Callable

from .profile import utc_now_iso
from .reporting_profile import PortfolioPhaseReadiness, PortfolioPhaseReport
from .serialization import read_json, write_json_atomic
from .service import PortfolioRegistryService
from .snapshot_service import PortfolioSnapshotService


class PortfolioPhaseReportingService:
    def __init__(
        self,
        *,
        registry_file: Path,
        snapshot_directory: Path,
        exposure_file: Path,
        audit_file: Path,
        lifecycle_file: Path,
        database_report_file: Path,
        session_factory: Callable | None = None,
    ) -> None:
        self.registry_file = registry_file
        self.snapshot_directory = snapshot_directory
        self.exposure_file = exposure_file
        self.audit_file = audit_file
        self.lifecycle_file = lifecycle_file
        self.database_report_file = database_report_file
        self.session_factory = session_factory

    def build_report(self) -> PortfolioPhaseReport:
        registry_service = PortfolioRegistryService(self.registry_file)
        registry = registry_service.load_snapshot()
        snapshot_service = PortfolioSnapshotService(
            registry_service=registry_service,
            snapshot_directory=self.snapshot_directory,
            exposure_file=self.exposure_file,
            audit_file=self.audit_file,
        )
        exposure = snapshot_service.build_exposure_view(registry).to_dict()
        lifecycle = read_json(self.lifecycle_file) if self.lifecycle_file.exists() else {}
        audit = snapshot_service.load_audit_history().to_dict()
        database = read_json(self.database_report_file) if self.database_report_file.exists() else {}
        readiness = self.evaluate_readiness(
            registry=registry.to_dict(), exposure=exposure, lifecycle=lifecycle,
            audit=audit, database=database,
        )
        return PortfolioPhaseReport(
            portfolio_id=registry.account.portfolio_id,
            generated_at=utc_now_iso(),
            phase="MILESTONE_36_PHASE_1",
            status=readiness.status,
            registry=registry.to_dict(),
            exposure=exposure,
            lifecycle=lifecycle,
            audit=audit,
            database=database,
            readiness=readiness,
            artifacts={
                "registry": str(self.registry_file),
                "exposure": str(self.exposure_file),
                "audit": str(self.audit_file),
                "lifecycle": str(self.lifecycle_file),
                "database_sync": str(self.database_report_file),
            },
        )

    def evaluate_readiness(
        self, *, registry: dict[str, Any], exposure: dict[str, Any],
        lifecycle: dict[str, Any], audit: dict[str, Any], database: dict[str, Any],
    ) -> PortfolioPhaseReadiness:
        unresolved = int(lifecycle.get("unresolved_exception_count", 0))
        checks = {
            "registry_available": bool(registry.get("account", {}).get("portfolio_id")),
            "cash_non_negative": float(registry.get("cash_balance", 0.0)) >= 0.0,
            "net_liquidation_positive": float(registry.get("net_liquidation_value", 0.0)) > 0.0,
            "identity_reconciled": unresolved == 0,
            "exposure_available": bool(exposure.get("portfolio_id")),
            "audit_history_available": bool(audit.get("records")),
            "database_sync_complete": database.get("status") == "COMPLETE",
        }
        warnings: list[str] = []
        if unresolved:
            warnings.append(f"UNRESOLVED_LIFECYCLE_EXCEPTIONS:{unresolved}")
        warnings.extend(str(item) for item in exposure.get("warnings", []))
        if not checks["database_sync_complete"]:
            warnings.append("DATABASE_SYNC_NOT_COMPLETE")
        status = "READY" if all(checks.values()) else "NOT_READY"
        return PortfolioPhaseReadiness(
            portfolio_id=str(registry.get("account", {}).get("portfolio_id", "")),
            generated_at=utc_now_iso(),
            status=status,
            checks=checks,
            warnings=tuple(dict.fromkeys(warnings)),
            details={
                "open_position_count": int(registry.get("open_position_count", 0)),
                "closed_position_count": int(registry.get("closed_position_count", 0)),
                "capital_utilization_pct": float(exposure.get("capital_utilization_pct", 0.0)),
            },
        )

    def write_report(self, json_file: Path, html_file: Path) -> PortfolioPhaseReport:
        report = self.build_report()
        write_json_atomic(json_file, report.to_dict())
        html_file.parent.mkdir(parents=True, exist_ok=True)
        html_file.write_text(self._render_html(report), encoding="utf-8")
        return report

    @staticmethod
    def _render_html(report: PortfolioPhaseReport) -> str:
        r = report.readiness
        rows = "".join(
            f"<tr><td>{html.escape(name)}</td><td>{'PASS' if passed else 'FAIL'}</td></tr>"
            for name, passed in r.checks.items()
        )
        warnings = "".join(f"<li>{html.escape(item)}</li>" for item in r.warnings) or "<li>None</li>"
        return f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Milestone 36 Phase 1 Portfolio Report</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;max-width:1100px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:8px;text-align:left}}.status{{font-size:1.4em;font-weight:bold}}</style></head>
<body><h1>Milestone 36 Phase 1 — Portfolio Management Foundation</h1>
<p class='status'>Phase status: {html.escape(report.status)}</p>
<p>Portfolio: {html.escape(report.portfolio_id)} | Generated: {html.escape(report.generated_at)}</p>
<h2>Readiness checks</h2><table><tr><th>Check</th><th>Result</th></tr>{rows}</table>
<h2>Portfolio summary</h2><ul>
<li>Cash balance: {report.registry.get('cash_balance', 0)}</li>
<li>Net liquidation value: {report.registry.get('net_liquidation_value', 0)}</li>
<li>Open positions: {report.registry.get('open_position_count', 0)}</li>
<li>Capital utilization: {report.exposure.get('capital_utilization_pct', 0)}%</li></ul>
<h2>Warnings</h2><ul>{warnings}</ul>
<h2>Artifacts</h2><pre>{html.escape(str(report.artifacts))}</pre></body></html>"""
