from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from trading_ai.scanner.universe_management import (
    AutomaticUniverseBuilderService,
    LiquidityGovernancePolicy,
    LiquidityGovernanceService,
    UniverseRefreshPolicy,
)
from trading_ai.scanner.market_data_population import BulkMarketDataPopulationService, MarketDataPopulationPolicy
from trading_ai.scanner.universe_management.liquidity_metrics_builder import (
    LiquidityMetricsBuildPolicy,
    LiquidityMetricsBuilder,
)

from .models import PipelineStage, PipelineStageResult, UniversePipelineResult
from .policy import UniversePipelinePolicy
from .serialization import artifact_health, pipeline_html, write_json_atomic


class UniversePipelineService:
    def __init__(self, policy: UniversePipelinePolicy | None = None) -> None:
        self.policy = policy or UniversePipelinePolicy()
        self.policy.validate()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _stage(stage: PipelineStage, action: Callable[[], tuple[str, str, dict[str, Any]]]) -> PipelineStageResult:
        started = datetime.now(timezone.utc)
        tick = time.perf_counter()
        status, message, details = action()
        completed = datetime.now(timezone.utc)
        return PipelineStageResult(stage=stage.value, status=status, started_at=started, completed_at=completed, elapsed_seconds=time.perf_counter() - tick, message=message, details=details)

    def run(
        self,
        *,
        providers,
        session=None,
        universe_dir: str | Path = "data/universe",
        market_dir: str | Path = "data/market",
        report_dir: str | Path = "reports/m35/phase1/pipeline",
        universe_refresh_report_dir: str | Path = "reports/m35/phase1/universe_refresh",
        liquidity_metrics_report_dir: str | Path = "reports/m35/phase1/liquidity_metrics",
        liquidity_report_dir: str | Path = "reports/m35/phase1/liquidity",
        reference_csv: str | Path | None = None,
        quote_csv: str | Path | None = None,
        resume: bool = False,
        dry_run: bool = False,
        report_only: bool = False,
        skip_universe_refresh: bool = False,
        skip_liquidity_metrics: bool = False,
        liquidity_policy: LiquidityGovernancePolicy | None = None,
        metrics_policy: LiquidityMetricsBuildPolicy | None = None,
        populate_market_data: bool = False,
        market_data_provider=None,
        market_data_policy: MarketDataPopulationPolicy | None = None,
        market_data_report_dir: str | Path = "reports/m35/phase1/market_data_population",
        market_data_resume: bool = False,
        market_data_force_refresh: bool = False,
        market_data_limit: int | None = None,
    ) -> UniversePipelineResult:
        started_at = self._now(); tick = time.perf_counter(); run_id = f"m35p1-{started_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        universe_dir = Path(universe_dir); market_dir = Path(market_dir); report_dir = Path(report_dir)
        checkpoint_path = report_dir / "checkpoints" / "checkpoint.json"
        prior = self._read_json(checkpoint_path) if resume else {}
        last_completed = str(prior.get("last_completed_stage", PipelineStage.INITIALIZING.value))
        stage_order = {stage.value: index for index, stage in enumerate((PipelineStage.INITIALIZING, PipelineStage.BUILDING_UNIVERSE, PipelineStage.POPULATING_MARKET_DATA, PipelineStage.BUILDING_LIQUIDITY_METRICS, PipelineStage.SCREENING_LIQUIDITY, PipelineStage.VALIDATING_PUBLICATION, PipelineStage.COMPLETE))}
        def resume_completed(stage: PipelineStage) -> bool:
            return bool(resume and stage_order.get(last_completed, 0) >= stage_order.get(stage.value, 0))
        stages: list[PipelineStageResult] = []; warnings: list[str] = []; error = ""
        universe_count = metrics_count = eligible_count = rejected_count = review_count = 0
        universe_rebuilt_this_run = False

        canonical_csv = universe_dir / "us_listed_equities_etfs.csv"
        universe_manifest = universe_dir / "universe_manifest.json"
        metrics_csv = market_dir / "liquidity_metrics.csv"
        metrics_manifest = market_dir / "liquidity_metrics_manifest.json"
        eligible_csv = universe_dir / "eligible_universe.csv"
        rejected_csv = universe_dir / "rejected_universe.csv"

        def checkpoint(stage: PipelineStage) -> None:
            nonlocal last_completed
            last_completed = stage.value
            write_json_atomic(checkpoint_path, {"run_id": run_id, "last_completed_stage": last_completed, "updated_at": self._now(), "resume_supported": True})

        try:
            if not report_only and not skip_universe_refresh and not resume_completed(PipelineStage.BUILDING_UNIVERSE):
                if not providers:
                    raise ValueError("At least one universe provider is required unless --report-only or --skip-universe-refresh is used.")
                def build_universe():
                    result = AutomaticUniverseBuilderService(UniverseRefreshPolicy(
                        minimum_symbol_count=self.policy.minimum_symbol_count,
                        maximum_source_age_hours=self.policy.maximum_source_age_hours,
                        allow_degraded_publish=not self.policy.strict_providers,
                    )).refresh(providers, output_dir=universe_dir, report_dir=universe_refresh_report_dir)
                    if not result.published:
                        raise RuntimeError(f"Universe publication rejected with status {result.status}")
                    warnings.extend(result.warnings); return result.status, f"Published {result.symbol_count} symbols", result.__dict__
                stage = self._stage(PipelineStage.BUILDING_UNIVERSE, build_universe)
                stages.append(stage)
                universe_count = int(stage.details.get("symbol_count", 0))
                universe_rebuilt_this_run = True
                checkpoint(PipelineStage.BUILDING_UNIVERSE)
            else:
                # The canonical CSV is authoritative when universe refresh is skipped.
                # Never derive its count from a potentially stale rebuild manifest.
                if canonical_csv.is_file():
                    with canonical_csv.open(encoding="utf-8-sig") as handle:
                        universe_count = max(0, sum(1 for _ in handle) - 1)
                else:
                    universe_count = 0

            if not report_only and populate_market_data and not resume_completed(PipelineStage.POPULATING_MARKET_DATA):
                if session is None:
                    raise ValueError("A database session is required to populate market data.")
                if market_data_provider is None:
                    raise ValueError("A market-data provider is required when populate_market_data is enabled.")
                def populate_prices():
                    result = BulkMarketDataPopulationService(
                        market_data_provider, market_data_policy or MarketDataPopulationPolicy()
                    ).run(
                        session=session, universe_csv=canonical_csv,
                        report_dir=market_data_report_dir, resume=market_data_resume,
                        force_refresh=market_data_force_refresh, limit=market_data_limit,
                    )
                    if result.status == "FAILED":
                        raise RuntimeError("Bulk market-data population failed")
                    if result.status != "READY":
                        warnings.extend(result.warnings)
                    return result.status, f"Coverage {result.coverage.coverage_pct:.2f}%", result.to_dict()
                stage = self._stage(PipelineStage.POPULATING_MARKET_DATA, populate_prices)
                stages.append(stage); checkpoint(PipelineStage.POPULATING_MARKET_DATA)

            if not report_only and not skip_liquidity_metrics and not resume_completed(PipelineStage.BUILDING_LIQUIDITY_METRICS):
                if session is None:
                    raise ValueError("A database session is required to build liquidity metrics.")
                def build_metrics():
                    result = LiquidityMetricsBuilder(metrics_policy or LiquidityMetricsBuildPolicy()).build(
                        session=session, universe_csv=canonical_csv, output_csv=metrics_csv,
                        manifest_json=metrics_manifest, diagnostics_json=Path(liquidity_metrics_report_dir) / "build_diagnostics.json",
                        reference_csv=reference_csv, quote_csv=quote_csv,
                    )
                    if result.status == "FAILED" or (result.status == "DEGRADED" and not self.policy.continue_on_degraded_metrics):
                        raise RuntimeError(f"Liquidity metrics build ended with status {result.status}")
                    if result.status != "READY": warnings.append(f"Liquidity metrics status is {result.status}")
                    return result.status, f"Published {result.metrics_count} metrics", result.__dict__
                stage = self._stage(PipelineStage.BUILDING_LIQUIDITY_METRICS, build_metrics); stages.append(stage); metrics_count = int(stage.details.get("metrics_count", 0)); checkpoint(PipelineStage.BUILDING_LIQUIDITY_METRICS)
            else:
                manifest = self._read_json(metrics_manifest); metrics_count = int(manifest.get("metrics_count", 0))

            if not report_only and not resume_completed(PipelineStage.SCREENING_LIQUIDITY):
                def screen_liquidity():
                    result = LiquidityGovernanceService(liquidity_policy or LiquidityGovernancePolicy()).screen(
                        universe_csv=canonical_csv, metrics_csv=metrics_csv, output_dir=universe_dir, report_dir=liquidity_report_dir,
                    )
                    if self.policy.require_nonempty_eligible_universe and result.eligible_count < 1:
                        raise RuntimeError("Liquidity governance produced no eligible symbols")
                    return result.status, f"Eligible {result.eligible_count}; rejected {result.rejected_count}; review {result.review_count}", result.__dict__
                stage = self._stage(PipelineStage.SCREENING_LIQUIDITY, screen_liquidity); stages.append(stage)
                eligible_count = int(stage.details.get("eligible_count", 0)); rejected_count = int(stage.details.get("rejected_count", 0)); review_count = int(stage.details.get("review_count", 0)); checkpoint(PipelineStage.SCREENING_LIQUIDITY)

            def validate_publication():
                nonlocal eligible_count, rejected_count
                # Only validate the canonical CSV against universe_manifest when this
                # invocation actually rebuilt/published the universe. In canonical-only
                # mode, the CSV is the source of truth and an older rebuild manifest may
                # legitimately describe a different historical artifact.
                universe_expected = ""
                if universe_rebuilt_this_run:
                    universe_expected = str(self._read_json(universe_manifest).get("csv_sha256", ""))

                metrics_expected = str(self._read_json(metrics_manifest).get("sha256", ""))
                items = [
                    artifact_health("canonical_universe", canonical_csv, universe_expected),
                    artifact_health("liquidity_metrics", metrics_csv, metrics_expected),
                    artifact_health("liquidity_metrics_manifest", metrics_manifest),
                    artifact_health("eligible_universe", eligible_csv),
                    artifact_health("rejected_universe", rejected_csv),
                ]
                # universe_manifest is mandatory only for a universe rebuilt in this run.
                if universe_rebuilt_this_run:
                    items.insert(1, artifact_health("universe_manifest", universe_manifest))

                invalid = [
                    item.name
                    for item in items
                    if not item.exists
                    or (self.policy.require_checksum_validation and not item.checksum_valid)
                ]
                if invalid:
                    raise RuntimeError("Publication validation failed: " + ", ".join(invalid))
                def row_count(path: Path) -> int:
                    with path.open(encoding="utf-8-sig") as handle: return max(0, sum(1 for _ in handle) - 1)
                eligible_count = eligible_count or row_count(eligible_csv); rejected_count = rejected_count or row_count(rejected_csv)
                return "READY", "All required artifacts exist and checksums validate", {"artifacts": [item.to_dict() for item in items]}
            stage = self._stage(PipelineStage.VALIDATING_PUBLICATION, validate_publication); stages.append(stage); checkpoint(PipelineStage.VALIDATING_PUBLICATION)
            artifacts = tuple(artifact_health(name, path) for name, path in (
                ("canonical_universe", canonical_csv), ("universe_manifest", universe_manifest),
                ("liquidity_metrics", metrics_csv), ("liquidity_metrics_manifest", metrics_manifest),
                ("eligible_universe", eligible_csv), ("rejected_universe", rejected_csv),
            ))
            if not universe_count:
                with canonical_csv.open(encoding="utf-8-sig") as handle: universe_count = max(0, sum(1 for _ in handle) - 1)
            if not metrics_count:
                with metrics_csv.open(encoding="utf-8-sig") as handle: metrics_count = max(0, sum(1 for _ in handle) - 1)
            status = "DEGRADED" if any(item.status == "DEGRADED" for item in stages) or warnings else "READY"
            last_completed = PipelineStage.COMPLETE.value
            if dry_run: warnings.append("Dry-run requested: orchestration used configured temporary/output paths supplied by caller; no special in-place rollback was required.")
        except Exception as exc:
            status = "FAILED"; error = f"{type(exc).__name__}: {exc}"
            stages.append(PipelineStageResult(stage=PipelineStage.FAILED.value, status="FAILED", started_at=self._now(), completed_at=self._now(), elapsed_seconds=0.0, message=error))
            artifacts = tuple(artifact_health(name, path) for name, path in (("canonical_universe", canonical_csv), ("liquidity_metrics", metrics_csv), ("eligible_universe", eligible_csv), ("rejected_universe", rejected_csv)))

        completed_at = self._now()
        result = UniversePipelineResult(run_id=run_id, started_at=started_at, completed_at=completed_at, status=status, last_completed_stage=last_completed, elapsed_seconds=time.perf_counter() - tick, universe_count=universe_count, metrics_count=metrics_count, eligible_count=eligible_count, rejected_count=rejected_count, review_count=review_count, stage_results=tuple(stages), artifacts=artifacts, warnings=tuple(dict.fromkeys(warnings)), error=error, resumed=resume, dry_run=dry_run)
        write_json_atomic(report_dir / "pipeline_summary.json", result.to_dict())
        write_json_atomic(report_dir / "pipeline_manifest.json", {"schema_version": "m35.phase1.pipeline.v1", "run": result.to_dict()})
        write_json_atomic(report_dir / "provider_health.json", {"status": "READY" if not error else "REVIEW", "warnings": result.warnings})
        write_json_atomic(report_dir / "cache_health.json", {"status": "READY", "note": "Provider cache health is reported by the Step 2 download manager and Step 3 reconciliation artifacts."})
        from trading_ai.scanner.universe_management.atomic_publisher import AtomicFilePublisher
        AtomicFilePublisher.publish_text(report_dir / "pipeline_summary.html", pipeline_html(result))
        if status != "FAILED":
            checkpoint(PipelineStage.COMPLETE)
        return result
