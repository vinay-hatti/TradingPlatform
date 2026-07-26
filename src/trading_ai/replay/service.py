from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import text

from trading_ai.lineage import new_run_id
from trading_ai.reporting.manifest import write_report_manifest
from trading_ai.reporting.context import ReportingContext

from .canonical import content_hash, index_items, native
from .profile import (
    DecisionReplayExecutor, ReplayComparison, ReplayPolicy, ReplayResult,
    ReplaySelector, ReplaySource, ScannerReplayExecutor,
)
from .repository import HistoricalReplayRepository


class HistoricalReplayService:
    def __init__(
        self,
        session_factory=None,
        *,
        repository_factory=HistoricalReplayRepository,
        scanner_executor: ScannerReplayExecutor | None = None,
        decision_executor: DecisionReplayExecutor | None = None,
        policy: ReplayPolicy | None = None,
    ) -> None:
        if session_factory is None:
            from trading_ai.database import SessionLocal
            session_factory = SessionLocal
        self.session_factory = session_factory
        self.repository_factory = repository_factory
        self.scanner_executor = scanner_executor
        self.decision_executor = decision_executor
        self.policy = policy or ReplayPolicy()

    @staticmethod
    def _normalize(items: Iterable[Any]) -> tuple[dict[str, Any], ...]:
        return tuple(native(item) for item in items)

    @staticmethod
    def _compare(category: str, baseline: tuple[dict[str, Any], ...], replay: tuple[dict[str, Any], ...]) -> list[ReplayComparison]:
        baseline_index = index_items(baseline, category)
        replay_index = index_items(replay, category)
        rows: list[ReplayComparison] = []
        for key in sorted(set(baseline_index) | set(replay_index)):
            left = baseline_index.get(key)
            right = replay_index.get(key)
            left_hash = content_hash(left) if left is not None else None
            right_hash = content_hash(right) if right is not None else None
            if left is None:
                status = "ADDED"
            elif right is None:
                status = "MISSING"
            else:
                status = "MATCH" if left_hash == right_hash else "CHANGED"
            rows.append(ReplayComparison(category, key, status, left_hash, right_hash, {
                "baseline_present": left is not None,
                "replay_present": right is not None,
            }))
        return rows

    def run(self, selector: ReplaySelector, *, mode: str = "snapshot") -> ReplayResult:
        started_at = datetime.now(timezone.utc)
        replay_run_id = new_run_id("replay")
        with self.session_factory() as session:
            source = self.repository_factory(session).load(selector)

        normalized_mode = mode.strip().lower()
        if normalized_mode not in {"snapshot", "execute"}:
            raise ValueError("Replay mode must be snapshot or execute")
        warnings: list[str] = []
        if normalized_mode == "snapshot":
            candidates = source.scanner_candidates
            decisions = source.decisions
        else:
            if self.scanner_executor is None:
                raise RuntimeError("Execute replay requires a scanner_executor")
            candidates = self._normalize(self.scanner_executor(source))
            if self.decision_executor is not None:
                decisions = self._normalize(self.decision_executor(source, candidates))
            else:
                decisions = source.decisions
                warnings.append("Decision executor was not supplied; persisted decisions were reconstructed without recomputation.")

        comparisons = self._compare("candidate", source.scanner_candidates, candidates)
        if source.decisions or decisions:
            comparisons.extend(self._compare("decision", source.decisions, decisions))
        elif not self.policy.allow_missing_decisions:
            comparisons.append(ReplayComparison("decision", "decision-set", "MISSING", None, None, {}))

        candidate_mismatch = any(x.category == "candidate" and x.status != "MATCH" for x in comparisons)
        decision_mismatch = any(x.category == "decision" and x.status != "MATCH" for x in comparisons)
        failed = (self.policy.require_candidate_match and candidate_mismatch) or (self.policy.require_decision_match and decision_mismatch)
        status = "FAILED" if failed else "READY"
        completed_at = datetime.now(timezone.utc)
        result = ReplayResult(
            replay_run_id=replay_run_id,
            mode=normalized_mode.upper(),
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            source=source,
            replay_candidates=candidates,
            replay_decisions=decisions,
            comparisons=tuple(comparisons),
            warnings=tuple(warnings),
            metadata={
                "candidate_count": len(candidates),
                "decision_count": len(decisions),
                "mismatch_count": sum(item.status != "MATCH" for item in comparisons),
            },
        )
        if self.policy.persist_replay:
            self._persist(result)
        return result

    def _persist(self, result: ReplayResult) -> None:
        source = result.source
        with self.session_factory() as session:
            session.execute(text("""
                INSERT INTO historical_replay_run(
                    replay_run_id, replay_mode, source_scanner_run_id, source_decision_run_id,
                    publication_name, ingestion_run_id, option_snapshot_id, market_state_hash,
                    scanner_version, decision_engine_version, policy_version,
                    started_at, completed_at, status, candidate_count, decision_count,
                    mismatch_count, warnings_json, metadata_json
                ) VALUES (
                    :replay_run_id, :replay_mode, :source_scanner_run_id, :source_decision_run_id,
                    :publication_name, :ingestion_run_id, :option_snapshot_id, :market_state_hash,
                    :scanner_version, :decision_engine_version, :policy_version,
                    :started_at, :completed_at, :status, :candidate_count, :decision_count,
                    :mismatch_count, :warnings_json, :metadata_json
                )
            """), {
                "replay_run_id": result.replay_run_id, "replay_mode": result.mode,
                "source_scanner_run_id": source.scanner_run_id, "source_decision_run_id": source.decision_run_id,
                "publication_name": source.publication_name, "ingestion_run_id": source.ingestion_run_id,
                "option_snapshot_id": source.option_snapshot_id, "market_state_hash": source.market_state_hash,
                "scanner_version": source.scanner_version, "decision_engine_version": source.decision_engine_version,
                "policy_version": source.policy_version, "started_at": result.started_at,
                "completed_at": result.completed_at, "status": result.status,
                "candidate_count": len(result.replay_candidates), "decision_count": len(result.replay_decisions),
                "mismatch_count": sum(x.status != "MATCH" for x in result.comparisons),
                "warnings_json": json.dumps(result.warnings), "metadata_json": json.dumps(result.metadata),
            })
            for comparison in result.comparisons:
                session.execute(text("""
                    INSERT INTO historical_replay_comparison(
                        replay_run_id, category, comparison_key, comparison_status,
                        baseline_hash, replay_hash, details_json
                    ) VALUES (
                        :replay_run_id, :category, :comparison_key, :comparison_status,
                        :baseline_hash, :replay_hash, :details_json
                    )
                """), {
                    "replay_run_id": result.replay_run_id, "category": comparison.category,
                    "comparison_key": comparison.key, "comparison_status": comparison.status,
                    "baseline_hash": comparison.baseline_hash, "replay_hash": comparison.replay_hash,
                    "details_json": json.dumps(comparison.details, sort_keys=True),
                })
            session.commit()

    def export(self, result: ReplayResult, output_dir: str | Path) -> dict[str, Path]:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        output = target / "historical_replay.json"
        payload = native(asdict(result))
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        context = ReportingContext(
            report_version=self.policy.report_version,
            publication_name=result.source.publication_name,
            publication_status=result.source.publication_status,
            ingestion_run_id=result.source.ingestion_run_id,
            scanner_run_id=result.source.scanner_run_id,
            decision_run_id=result.source.decision_run_id,
            market_as_of_date=result.source.market_as_of_date,
            option_snapshot_id=result.source.option_snapshot_id,
            option_snapshot_timestamp=result.source.option_snapshot_timestamp,
            market_intelligence_snapshot_timestamp=result.source.market_intelligence_snapshot_timestamp,
            market_state_hash=result.source.market_state_hash,
            scanner_version=result.source.scanner_version,
            decision_engine_version=result.source.decision_engine_version,
            policy_version=result.source.policy_version,
        )
        manifest = write_report_manifest(
            target / "historical_replay_manifest.json",
            context=context,
            artifacts=[output],
            report_type="historical_replay",
            extra={"replay_run_id": result.replay_run_id, "mode": result.mode, "status": result.status, **result.metadata},
        )
        return {"json": output, "manifest": manifest}
