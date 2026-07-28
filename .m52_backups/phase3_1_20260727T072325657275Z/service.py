from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from sqlalchemy import text

from trading_ai.lineage.profile import DecisionRunLineage, PersistenceSummary, ScannerRunLineage


def _native(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {k: _native(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_native(v) for v in value]
    if hasattr(value, "item"):
        try:
            return _native(value.item())
        except Exception:
            pass
    return str(value)


def _json(value: Any) -> str:
    return json.dumps(_native(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def new_run_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:10]}"


class LineagePersistenceService:
    def __init__(self, session_factory: Callable[[], Any] | None = None):
        if session_factory is None:
            from trading_ai.database import SessionLocal
            session_factory = SessionLocal
        self.session_factory = session_factory

    def persist_scanner_run(
        self,
        lineage: ScannerRunLineage,
        candidates: Iterable[Any],
        *,
        metadata: dict[str, Any] | None = None,
        completed_at: datetime | None = None,
        status: str = "READY",
    ) -> PersistenceSummary:
        items = list(candidates)
        completed_at = completed_at or datetime.now(timezone.utc)
        metadata = dict(metadata or {})
        state_hash = _hash({
            "publication_name": lineage.publication_name,
            "ingestion_run_id": lineage.ingestion_run_id,
            "market_intelligence_snapshot_timestamp": lineage.market_intelligence_snapshot_timestamp,
            "option_snapshot_id": lineage.option_snapshot_id,
        })
        with self.session_factory() as session:
            session.execute(text("""
                INSERT INTO scanner_lineage_run(
                    scanner_run_id, publication_name, ingestion_run_id, publication_status,
                    published_at, market_as_of_date, market_intelligence_snapshot_timestamp,
                    option_snapshot_timestamp, option_snapshot_id, option_snapshot_completeness_pct,
                    published_state_degraded, scanner_version, market_state_hash,
                    started_at, completed_at, status, candidate_count, metadata_json
                ) VALUES (
                    :scanner_run_id, :publication_name, :ingestion_run_id, :publication_status,
                    :published_at, :market_as_of_date, :market_intelligence_snapshot_timestamp,
                    :option_snapshot_timestamp, :option_snapshot_id, :option_snapshot_completeness_pct,
                    :published_state_degraded, :scanner_version, :market_state_hash,
                    :started_at, :completed_at, :status, :candidate_count, :metadata_json
                )
            """), {
                **asdict(lineage), "market_state_hash": state_hash,
                "completed_at": completed_at, "status": status,
                "candidate_count": len(items), "metadata_json": _json(metadata),
            })
            for rank, item in enumerate(items, start=1):
                payload = _native(item)
                candidate_id = getattr(item, "candidate_id", None) or f"cand-{uuid.uuid5(uuid.NAMESPACE_URL, lineage.scanner_run_id + ':' + str(rank) + ':' + str(getattr(item, 'symbol', 'UNKNOWN'))).hex}"
                try:
                    setattr(item, "scanner_run_id", lineage.scanner_run_id)
                    setattr(item, "candidate_id", candidate_id)
                    setattr(item, "market_state_hash", state_hash)
                    setattr(item, "scanner_version", lineage.scanner_version)
                except Exception:
                    pass
                session.execute(text("""
                    INSERT INTO scanner_candidate_lineage(
                        candidate_id, scanner_run_id, rank, symbol, signal, strategy,
                        score, accepted, publication_name, ingestion_run_id,
                        market_intelligence_snapshot_timestamp, option_snapshot_id,
                        market_state_hash, scanner_version, payload_json
                    ) VALUES (
                        :candidate_id, :scanner_run_id, :rank, :symbol, :signal, :strategy,
                        :score, :accepted, :publication_name, :ingestion_run_id,
                        :market_intelligence_snapshot_timestamp, :option_snapshot_id,
                        :market_state_hash, :scanner_version, :payload_json
                    )
                """), {
                    "candidate_id": candidate_id, "scanner_run_id": lineage.scanner_run_id,
                    "rank": rank, "symbol": getattr(item, "symbol", None),
                    "signal": getattr(item, "signal", None), "strategy": getattr(item, "strategy", None),
                    "score": float(getattr(item, "ai_score", getattr(item, "final_score", 0.0)) or 0.0),
                    "accepted": True, "publication_name": lineage.publication_name,
                    "ingestion_run_id": lineage.ingestion_run_id,
                    "market_intelligence_snapshot_timestamp": lineage.market_intelligence_snapshot_timestamp,
                    "option_snapshot_id": lineage.option_snapshot_id, "market_state_hash": state_hash,
                    "scanner_version": lineage.scanner_version, "payload_json": _json(payload),
                })
            session.commit()
        return PersistenceSummary(lineage.scanner_run_id, 1, len(items), status, {"market_state_hash": state_hash})

    def persist_decision_run(
        self,
        lineage: DecisionRunLineage,
        result: Any,
        *,
        metadata: dict[str, Any] | None = None,
        completed_at: datetime | None = None,
    ) -> PersistenceSummary:
        decisions = list(getattr(result, "decisions", []) or [])
        completed_at = completed_at or datetime.now(timezone.utc)
        metadata = dict(metadata or {})
        state_hash = _hash({
            "publication_name": lineage.publication_name,
            "ingestion_run_id": lineage.ingestion_run_id,
            "market_intelligence_snapshot_timestamp": lineage.market_intelligence_snapshot_timestamp,
            "option_snapshot_id": lineage.option_snapshot_id,
        })
        with self.session_factory() as session:
            session.execute(text("""
                INSERT INTO institutional_decision_lineage_run(
                    decision_run_id, publication_name, ingestion_run_id, publication_status,
                    market_intelligence_snapshot_timestamp, option_snapshot_timestamp,
                    option_snapshot_id, published_state_degraded, decision_engine_version,
                    policy_version, market_state_hash, started_at, completed_at,
                    status, decision_count, metadata_json
                ) VALUES (
                    :decision_run_id, :publication_name, :ingestion_run_id, :publication_status,
                    :market_intelligence_snapshot_timestamp, :option_snapshot_timestamp,
                    :option_snapshot_id, :published_state_degraded, :decision_engine_version,
                    :policy_version, :market_state_hash, :started_at, :completed_at,
                    :status, :decision_count, :metadata_json
                )
            """), {
                **asdict(lineage), "market_state_hash": state_hash, "completed_at": completed_at,
                "status": getattr(result, "overall_readiness", "READY"),
                "decision_count": len(decisions), "metadata_json": _json(metadata),
            })
            for rank, decision in enumerate(decisions, start=1):
                candidate_id = getattr(decision, "candidate_id", None)
                scanner_run_id = getattr(decision, "scanner_run_id", None)
                decision_id = getattr(decision, "decision_id", None) or f"decision-{uuid.uuid5(uuid.NAMESPACE_URL, lineage.decision_run_id + ':' + str(rank) + ':' + str(getattr(decision, 'symbol', 'UNKNOWN'))).hex}"
                try:
                    setattr(decision, "decision_run_id", lineage.decision_run_id)
                    setattr(decision, "decision_id", decision_id)
                    setattr(decision, "market_state_hash", state_hash)
                    setattr(decision, "decision_engine_version", lineage.decision_engine_version)
                    setattr(decision, "policy_version", lineage.policy_version)
                except Exception:
                    pass
                session.execute(text("""
                    INSERT INTO institutional_decision_lineage(
                        decision_id, decision_run_id, scanner_run_id, candidate_id,
                        symbol, strategy, action, confidence, accepted,
                        publication_name, ingestion_run_id,
                        market_intelligence_snapshot_timestamp, option_snapshot_id,
                        market_state_hash, decision_engine_version, policy_version, payload_json
                    ) VALUES (
                        :decision_id, :decision_run_id, :scanner_run_id, :candidate_id,
                        :symbol, :strategy, :action, :confidence, :accepted,
                        :publication_name, :ingestion_run_id,
                        :market_intelligence_snapshot_timestamp, :option_snapshot_id,
                        :market_state_hash, :decision_engine_version, :policy_version, :payload_json
                    )
                """), {
                    "decision_id": decision_id, "decision_run_id": lineage.decision_run_id,
                    "scanner_run_id": scanner_run_id, "candidate_id": candidate_id,
                    "symbol": getattr(decision, "symbol", None),
                    "strategy": getattr(decision, "strategy_name", getattr(decision, "strategy", None)),
                    "action": getattr(decision, "action", getattr(decision, "recommendation", None)),
                    "confidence": float(getattr(decision, "confidence_score", getattr(decision, "confidence", 0.0)) or 0.0),
                    "accepted": bool(getattr(decision, "accepted", getattr(decision, "allowed", True))),
                    "publication_name": lineage.publication_name, "ingestion_run_id": lineage.ingestion_run_id,
                    "market_intelligence_snapshot_timestamp": lineage.market_intelligence_snapshot_timestamp,
                    "option_snapshot_id": lineage.option_snapshot_id, "market_state_hash": state_hash,
                    "decision_engine_version": lineage.decision_engine_version, "policy_version": lineage.policy_version,
                    "payload_json": _json(decision),
                })
            session.commit()
        return PersistenceSummary(lineage.decision_run_id, 1, len(decisions), str(getattr(result, "overall_readiness", "READY")), {"market_state_hash": state_hash})
