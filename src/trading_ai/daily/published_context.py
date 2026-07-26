from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from trading_ai.published_state.profile import PublishedMarketState


@dataclass(frozen=True)
class ScannerPublishedStateContext:
    publication_name: str
    ingestion_run_id: str
    publication_status: str
    published_at: str
    market_as_of_date: str
    market_intelligence_snapshot_timestamp: str
    option_snapshot_timestamp: str
    option_snapshot_id: str
    scanner_ready: bool
    decision_context_ready: bool
    option_snapshot_completeness_pct: float | None = None
    degraded: bool = False

    @classmethod
    def from_state(cls, state: PublishedMarketState) -> "ScannerPublishedStateContext":
        completeness = None
        details: dict[str, Any] = state.details or {}
        checks = details.get("checks", [])
        if isinstance(checks, list):
            for check in checks:
                if isinstance(check, dict) and check.get("name") == "option_snapshot_completeness":
                    try:
                        completeness = float(check.get("latest_value"))
                    except (TypeError, ValueError):
                        completeness = None
                    break
        return cls(
            publication_name=state.publication_name,
            ingestion_run_id=state.run_id,
            publication_status=state.readiness_status,
            published_at=state.published_at.isoformat(),
            market_as_of_date=state.as_of_date.isoformat(),
            market_intelligence_snapshot_timestamp=state.market_intelligence_timestamp.isoformat(),
            option_snapshot_timestamp=(state.option_snapshot_timestamp.isoformat() if state.option_snapshot_timestamp else ""),
            option_snapshot_id=state.option_snapshot_id or "",
            scanner_ready=state.scanner_ready,
            decision_context_ready=state.decision_context_ready,
            option_snapshot_completeness_pct=completeness,
            degraded=state.degraded,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def candidate_fields(self) -> dict[str, Any]:
        return {
            "publication_name": self.publication_name,
            "ingestion_run_id": self.ingestion_run_id,
            "publication_status": self.publication_status,
            "published_at": self.published_at,
            "market_as_of_date": self.market_as_of_date,
            "market_intelligence_snapshot_timestamp": self.market_intelligence_snapshot_timestamp,
            "option_snapshot_timestamp": self.option_snapshot_timestamp,
            "option_snapshot_id": self.option_snapshot_id,
            "option_snapshot_completeness_pct": self.option_snapshot_completeness_pct,
            "published_state_degraded": self.degraded,
        }
