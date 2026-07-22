from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from .atomic_publisher import AtomicFilePublisher
from .builder_profile import UniverseArtifactPaths, UniverseRefreshPolicy, UniverseRefreshResult
from .builder_serialization import canonical_csv_text, manifest_payload, refresh_report_html, sha256_text, summary_payload, write_json_atomic
from .reconciliation_serialization import write_reconciliation_json
from .reconciliation_service import UniverseReconciliationService
from .universe_engine import UniverseEngine
from .universe_policy import UniversePolicy


class AutomaticUniverseBuilderService:
    def __init__(self, policy: UniverseRefreshPolicy | None = None) -> None:
        self.policy = policy or UniverseRefreshPolicy()
        self.policy.validate()

    @staticmethod
    def _existing_symbols(path: Path) -> set[str]:
        if not path.is_file():
            return set()
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return {str(row.get("symbol", "")).strip().upper() for row in csv.DictReader(handle) if row.get("symbol")}

    def refresh(self, providers, *, output_dir: str | Path = "data/universe", report_dir: str | Path = "reports/m35/phase1/universe_refresh") -> UniverseRefreshResult:
        generated_at = datetime.now(timezone.utc)
        output = Path(output_dir)
        reports = Path(report_dir)
        paths = UniverseArtifactPaths(
            canonical_csv=output / "us_listed_equities_etfs.csv",
            manifest_json=output / "universe_manifest.json",
            summary_json=output / "universe_summary.json",
            reconciliation_json=reports / "provider_reconciliation.json",
            refresh_report_html=reports / "universe_refresh_report.html",
        )
        reconciliation = UniverseReconciliationService().fetch_and_reconcile(providers)
        build = UniverseEngine(UniversePolicy(minimum_symbol_count=self.policy.minimum_symbol_count)).build(
            reconciliation.securities, generated_at=generated_at
        )
        previous = self._existing_symbols(paths.canonical_csv)
        current = {item.symbol for item in build.universe.securities}
        stale = 0
        warnings = list(build.universe.warnings)
        for result in reconciliation.provider_results:
            age_hours = max(0.0, (generated_at - result.fetched_at).total_seconds() / 3600)
            if age_hours > self.policy.maximum_source_age_hours:
                stale += 1
                warnings.append(f"Provider {result.provider_name} source age is {age_hours:.1f} hours.")
            if result.warning:
                warnings.append(f"{result.provider_name}: {result.warning}")
        valid_count = len(current) >= self.policy.minimum_symbol_count
        has_source = bool(current) and (not self.policy.require_at_least_one_provider or bool(reconciliation.provider_results))
        degraded = reconciliation.failed_provider_count > 0 or stale > 0
        publish_allowed = valid_count and has_source and (self.policy.allow_degraded_publish or not degraded)
        status = "READY" if publish_allowed and not degraded else ("DEGRADED" if publish_allowed else "REJECTED")
        artifacts = {
            "canonical_csv": str(paths.canonical_csv),
            "manifest_json": str(paths.manifest_json),
            "summary_json": str(paths.summary_json),
            "reconciliation_json": str(paths.reconciliation_json),
            "refresh_report_html": str(paths.refresh_report_html),
        }
        result = UniverseRefreshResult(
            generated_at=generated_at, status=status, published=publish_allowed,
            symbol_count=len(current), added_count=len(current - previous),
            removed_count=len(previous - current), unchanged_count=len(previous & current),
            stale_provider_count=stale, failed_provider_count=reconciliation.failed_provider_count,
            source_names=build.universe.source_names, warnings=tuple(dict.fromkeys(warnings)),
            artifacts=artifacts,
            metadata={"provider_governance_status": reconciliation.governance_status, "universe_governance_status": build.universe.governance_status},
        )
        paths.reconciliation_json.parent.mkdir(parents=True, exist_ok=True)
        write_reconciliation_json(reconciliation, paths.reconciliation_json)
        if publish_allowed:
            csv_text = canonical_csv_text(build)
            AtomicFilePublisher.publish_text(paths.canonical_csv, csv_text)
            digest = sha256_text(csv_text)
            write_json_atomic(paths.manifest_json, manifest_payload(build=build, reconciliation=reconciliation, refresh=result, csv_sha256=digest))
            write_json_atomic(paths.summary_json, summary_payload(result, build))
        else:
            warnings_path = reports / "rejected_refresh_summary.json"
            write_json_atomic(warnings_path, summary_payload(result, build))
        AtomicFilePublisher.publish_text(paths.refresh_report_html, refresh_report_html(result))
        return result
