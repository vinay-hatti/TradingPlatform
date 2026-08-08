from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from .models import StockScannerPublicationModel, StockScannerRunModel
from .repository import StockIntelligenceRepository
from .service import StockIntelligenceService


class StockScannerOrchestrator:
    """Additive Milestone 61 scanner orchestration over persisted Polygon inputs."""

    def __init__(self, session, intelligence_service: StockIntelligenceService | None = None):
        self.session = session
        self.intelligence = intelligence_service or StockIntelligenceService()
        self.repository = StockIntelligenceRepository(session)

    def run(
        self,
        data_by_symbol: dict[str, dict],
        *,
        external_context_by_symbol: dict[str, dict] | None = None,
        publication_name: str = "current_stock_intelligence",
        minimum_score: float = 0.0,
        top: int | None = None,
        snapshot_timestamp: str | None = None,
        lineage: dict | None = None,
    ) -> dict:
        timestamp = snapshot_timestamp or datetime.now(timezone.utc).isoformat()
        lineage_payload = dict(lineage or {})
        run_id = f"stock-scan-{uuid4().hex}"
        run = StockScannerRunModel(
            id=run_id,
            symbol="*",
            scanner_run_id=run_id,
            candidate_id=None,
            snapshot_timestamp=timestamp,
            status="RUNNING",
            provider="polygon",
            payload_json={"symbol_count": len(data_by_symbol), "publication_name": publication_name, "source": "persisted_polygon_price_history", "timeframes": sorted({tf for values in data_by_symbol.values() for tf in values}), "lineage": lineage_payload},
        )
        self.session.add(run)
        profiles = []
        failures = []
        contexts = external_context_by_symbol or {}
        for symbol in sorted(data_by_symbol):
            try:
                profile = self.intelligence.analyze(
                    symbol,
                    data_by_symbol[symbol],
                    snapshot_timestamp=timestamp,
                    external_context=contexts.get(symbol),
                )
                if profile.scores and profile.scores.overall >= minimum_score:
                    profiles.append(profile)
            except Exception as exc:  # scanner continues across isolated symbol failures
                failures.append({"symbol": symbol, "error": str(exc), "type": type(exc).__name__})
        profiles.sort(key=lambda item: (-float(item.scores.overall), item.symbol))
        if top is not None and int(top) > 0:
            profiles = profiles[: int(top)]
        for rank, profile in enumerate(profiles, start=1):
            candidate_id = f"stock-candidate-{uuid4().hex}"
            profile.metadata.update({"rank": rank, "publication_name": publication_name, "scanner_run_id": run_id})
            self.repository.save_profile(run_id, candidate_id, profile)
        status = "READY" if profiles and not failures else ("DEGRADED" if profiles else "FAILED")
        run.status = status
        run.payload_json = {
            **dict(run.payload_json or {}),
            "candidate_count": len(profiles),
            "failure_count": len(failures),
            "failures": failures,
        }
        publication_id = f"stock-publication-{uuid4().hex}"
        publication = StockScannerPublicationModel(
            id=publication_id,
            symbol="*",
            scanner_run_id=run_id,
            candidate_id=None,
            snapshot_timestamp=timestamp,
            publication_name=publication_name,
            status=status,
            payload_json={
                "run_id": run_id,
                "candidate_count": len(profiles),
                "symbols": [item.symbol for item in profiles],
                "state_hashes": [item.state_hash for item in profiles],
                "source": "persisted_polygon_price_history",
                "timeframes": sorted({tf for values in data_by_symbol.values() for tf in values}),
                "context_sources": ["market_overview_snapshot", "stock_trend_snapshot", "stock_trend_forecast_snapshot", "dealer_position_snapshot"],
                "lineage": lineage_payload,
            },
        )
        self.session.add(publication)
        self.session.commit()
        return {
            "run_id": run_id,
            "publication_id": publication_id,
            "publication_name": publication_name,
            "snapshot_timestamp": timestamp,
            "status": status,
            "candidate_count": len(profiles),
            "failures": failures,
            "candidates": [asdict(item) if hasattr(item, "__dataclass_fields__") else dict(vars(item)) for item in profiles],
        }
