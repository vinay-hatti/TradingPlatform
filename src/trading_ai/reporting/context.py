from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping


REPORT_VERSION = "m47.phase6.v1"


@dataclass(frozen=True)
class ReportingContext:
    report_version: str = REPORT_VERSION
    publication_name: str | None = None
    publication_status: str = "UNKNOWN"
    published_at: str | None = None
    ingestion_run_id: str | None = None
    scanner_run_id: str | None = None
    decision_run_id: str | None = None
    market_as_of_date: str | None = None
    option_snapshot_id: str | None = None
    option_snapshot_timestamp: str | None = None
    market_intelligence_snapshot_timestamp: str | None = None
    option_snapshot_completeness_pct: float | None = None
    scanner_ready: bool | None = None
    decision_context_ready: bool | None = None
    published_state_degraded: bool = False
    market_state_hash: str | None = None
    scanner_version: str | None = None
    decision_engine_version: str | None = None
    policy_version: str | None = None
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not payload["generated_at"]:
            payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, Any] | None) -> "ReportingContext":
        metadata = dict(metadata or {})
        published = metadata.get("published_state") or metadata.get("published_market_state") or {}
        if not isinstance(published, Mapping):
            published = {}

        def pick(name: str, default: Any = None) -> Any:
            value = metadata.get(name)
            if value is None:
                value = published.get(name)
            return default if value is None else value

        completeness = pick("option_snapshot_completeness_pct")
        try:
            completeness = float(completeness) if completeness not in (None, "") else None
        except (TypeError, ValueError):
            completeness = None

        market_state_hash = pick("market_state_hash")
        if not market_state_hash:
            stable = {
                "publication_name": pick("publication_name"),
                "ingestion_run_id": pick("ingestion_run_id"),
                "published_at": pick("published_at"),
                "market_as_of_date": pick("market_as_of_date"),
                "option_snapshot_id": pick("option_snapshot_id"),
                "market_intelligence_snapshot_timestamp": pick("market_intelligence_snapshot_timestamp"),
            }
            market_state_hash = sha256(
                json.dumps(stable, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()

        return cls(
            publication_name=pick("publication_name"),
            publication_status=str(pick("publication_status", "BYPASSED")),
            published_at=pick("published_at"),
            ingestion_run_id=pick("ingestion_run_id"),
            scanner_run_id=pick("scanner_run_id"),
            decision_run_id=pick("decision_run_id"),
            market_as_of_date=pick("market_as_of_date"),
            option_snapshot_id=pick("option_snapshot_id"),
            option_snapshot_timestamp=pick("option_snapshot_timestamp"),
            market_intelligence_snapshot_timestamp=pick("market_intelligence_snapshot_timestamp"),
            option_snapshot_completeness_pct=completeness,
            scanner_ready=pick("scanner_ready"),
            decision_context_ready=pick("decision_context_ready"),
            published_state_degraded=bool(pick("published_state_degraded", pick("degraded", False))),
            market_state_hash=str(market_state_hash),
            scanner_version=pick("scanner_version"),
            decision_engine_version=pick("decision_engine_version"),
            policy_version=pick("policy_version"),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
