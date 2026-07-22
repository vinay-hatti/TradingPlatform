from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .atomic_publisher import AtomicFilePublisher
from .liquidity_engine import LiquidityGovernanceEngine
from .liquidity_metrics_provider import CsvLiquidityMetricsProvider
from .liquidity_policy import LiquidityGovernancePolicy
from .liquidity_profile import LiquidityScreenResult
from .liquidity_serialization import evaluations_csv, report_html, write_json


class LiquidityGovernanceService:
    def __init__(self, policy: LiquidityGovernancePolicy | None = None) -> None:
        self.policy = policy or LiquidityGovernancePolicy()
        self.engine = LiquidityGovernanceEngine(self.policy)

    @staticmethod
    def _load_universe(path: Path) -> list[dict[str, str]]:
        if not path.is_file():
            raise FileNotFoundError(f"Canonical universe not found: {path}. Run update-universe first.")
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def screen(self, *, universe_csv: str | Path = "data/universe/us_listed_equities_etfs.csv", metrics_csv: str | Path, output_dir: str | Path = "data/universe", report_dir: str | Path = "reports/m35/phase1/liquidity") -> LiquidityScreenResult:
        generated_at = datetime.now(timezone.utc)
        securities = self._load_universe(Path(universe_csv))
        metrics = CsvLiquidityMetricsProvider(metrics_csv).load()
        evaluations = tuple(self.engine.evaluate(item, metrics.get(str(item.get("symbol", "")).upper()), now=generated_at) for item in securities)
        eligible = tuple(item for item in evaluations if item.eligible)
        rejected = tuple(item for item in evaluations if item.status == "REJECTED")
        review = tuple(item for item in evaluations if item.status == "REVIEW")
        breakdown = Counter(reason for item in evaluations for reason in item.rejection_reasons)
        output = Path(output_dir); reports = Path(report_dir)
        artifacts = {
            "eligible_universe_csv": str(output / "eligible_universe.csv"),
            "rejected_universe_csv": str(output / "rejected_universe.csv"),
            "liquidity_summary_json": str(output / "liquidity_summary.json"),
            "liquidity_statistics_json": str(reports / "liquidity_statistics.json"),
            "rejection_breakdown_csv": str(reports / "rejection_breakdown.csv"),
            "liquidity_report_html": str(reports / "liquidity_governance_report.html"),
        }
        result = LiquidityScreenResult(
            generated_at=generated_at, status="READY" if eligible else "REVIEW",
            evaluated_count=len(evaluations), eligible_count=len(eligible), rejected_count=len(rejected), review_count=len(review),
            missing_metrics_count=breakdown.get("MISSING_METRICS", 0), stale_metrics_count=breakdown.get("STALE_MARKET_DATA", 0),
            evaluations=evaluations, rejection_breakdown=dict(breakdown), artifacts=artifacts,
        )
        AtomicFilePublisher.publish_text(Path(artifacts["eligible_universe_csv"]), evaluations_csv(eligible))
        AtomicFilePublisher.publish_text(Path(artifacts["rejected_universe_csv"]), evaluations_csv(tuple(item for item in evaluations if not item.eligible)))
        write_json(Path(artifacts["liquidity_summary_json"]), {key: value for key, value in result.__dict__.items() if key != "evaluations"})
        write_json(Path(artifacts["liquidity_statistics_json"]), {"generated_at": generated_at, "evaluated_count": len(evaluations), "eligible_count": len(eligible), "rejected_count": len(rejected), "review_count": len(review), "rejection_breakdown": dict(breakdown)})
        breakdown_csv = "reason,count\n" + "".join(f"{reason},{count}\n" for reason, count in sorted(breakdown.items(), key=lambda pair: (-pair[1], pair[0])))
        AtomicFilePublisher.publish_text(Path(artifacts["rejection_breakdown_csv"]), breakdown_csv)
        AtomicFilePublisher.publish_text(Path(artifacts["liquidity_report_html"]), report_html(result))
        return result
