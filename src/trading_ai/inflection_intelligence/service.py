from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
import time
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.exc import OperationalError

from trading_ai.database.models import PriceHistory
from trading_ai.institutional_options.models import InstitutionalDecisionSnapshotModel, InstitutionalOpportunityModel
from trading_ai.institutional_market_structure.database_models import DealerPositionSnapshotModel
from trading_ai.stock_intelligence.models import StockScannerCandidateModel, StockScannerPublicationModel

from .engine import Bar, InstitutionalInflectionEngine
from .models import InflectionPublicationModel, InflectionSnapshotModel, InflectionTimelineEventModel


class InstitutionalInflectionService:
    PUBLICATION = "current_institutional_inflection"

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.engine = InstitutionalInflectionEngine()

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _latest_stock_run(self, session) -> str:
        row = session.execute(
            select(StockScannerPublicationModel).where(
                StockScannerPublicationModel.publication_name == "current_stock_intelligence",
                StockScannerPublicationModel.status == "READY",
            ).order_by(desc(StockScannerPublicationModel.snapshot_timestamp))
        ).scalars().first()
        if not row:
            raise LookupError("No READY current_stock_intelligence publication found")
        return row.scanner_run_id

    def _dealer_payload(self, session, symbol: str) -> dict:
        row = session.execute(
            select(DealerPositionSnapshotModel).where(DealerPositionSnapshotModel.symbol == symbol)
            .order_by(desc(DealerPositionSnapshotModel.as_of_date))
        ).scalars().first()
        if not row:
            return {}
        positioning = float(row.institutional_positioning_score or 50.0)
        migration = 50.0
        if row.gamma_flip_distance_pct is not None:
            migration = max(0.0, min(100.0, 100.0 - abs(float(row.gamma_flip_distance_pct)) * 8.0))
        hedge = max(0.0, min(100.0, 50.0 + float(row.net_vanna_exposure or 0.0) / 1_000_000.0 + float(row.net_charm_exposure or 0.0) / 1_000_000.0))
        return {
            "gamma_score": positioning,
            "wall_migration_score": migration,
            "hedge_pressure_score": hedge,
            "gamma_regime": row.gamma_regime,
            "gamma_flip": row.gamma_flip,
            "put_wall": row.primary_put_wall,
            "call_wall": row.primary_call_wall,
        }

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, ceil((percentile / 100.0) * len(ordered)) - 1))
        return round(float(ordered[index]), 4)

    @classmethod
    def _diagnostics(cls, scores: list[float], transitions: dict[str, int], directions: dict[str, int], components: dict[str, list[float]]) -> dict:
        histogram = {f"{lo:02d}-{lo+9:02d}": 0 for lo in range(0, 100, 10)}
        histogram["100"] = 0
        for score in scores:
            histogram["100" if score >= 100 else f"{int(score // 10) * 10:02d}-{int(score // 10) * 10 + 9:02d}"] += 1
        return {
            "minimum": round(min(scores), 4) if scores else 0.0,
            "p25": cls._percentile(scores, 25),
            "median": cls._percentile(scores, 50),
            "p75": cls._percentile(scores, 75),
            "p90": cls._percentile(scores, 90),
            "p95": cls._percentile(scores, 95),
            "maximum": round(max(scores), 4) if scores else 0.0,
            "histogram": histogram,
            "transition_counts": transitions,
            "direction_counts": directions,
            "component_averages": {name: round(sum(vals) / len(vals), 4) if vals else 0.0 for name, vals in components.items()},
            "thresholds": {"high_conviction": 80.0, "actionable": 70.0, "watch": 60.0, "developing": 50.0},
            "classifications": {
                "HIGH_CONVICTION": sum(v >= 80 for v in scores),
                "ACTIONABLE": sum(70 <= v < 80 for v in scores),
                "WATCH": sum(60 <= v < 70 for v in scores),
                "DEVELOPING": sum(50 <= v < 60 for v in scores),
                "LOW_SIGNAL": sum(v < 50 for v in scores),
            },
        }

    def build(self, *, limit: int | None = None, timeframe: str = "1d", build_mode: str = "MANUAL", max_retries: int = 3) -> dict:
        for attempt in range(1, max_retries + 1):
            try:
                return self._build_once(limit=limit, timeframe=timeframe, build_mode=build_mode)
            except OperationalError:
                if attempt >= max_retries:
                    raise
                try:
                    self.session_factory.kw.get("bind").dispose()
                except Exception:
                    pass
                time.sleep(min(2 ** (attempt - 1), 4))
        raise RuntimeError("Inflection build retry loop exhausted")

    def _build_once(self, *, limit: int | None, timeframe: str, build_mode: str) -> dict:
        with self.session_factory() as session:
            source_run = self._latest_stock_run(session)
            query = select(StockScannerCandidateModel).where(StockScannerCandidateModel.scanner_run_id == source_run).order_by(desc(StockScannerCandidateModel.score))
            if limit:
                query = query.limit(limit)
            candidates = session.execute(query).scalars().all()
            built = 0; skipped = 0; high = 0; scores: list[float] = []
            transitions: dict[str, int] = {}
            directions: dict[str, int] = {}
            component_values: dict[str, list[float]] = {k: [] for k in ("trend","structure","dealer","volatility","participation","breadth","liquidity")}
            published_at = self.now()
            for candidate in candidates:
                bars_rows = session.execute(
                    select(PriceHistory).where(PriceHistory.symbol == candidate.symbol).order_by(PriceHistory.date.desc()).limit(90)
                ).scalars().all()
                if len(bars_rows) < 25:
                    skipped += 1; continue
                bars = [Bar(float(r.close or 0), float(r.high or r.close or 0), float(r.low or r.close or 0), float(r.volume or 0)) for r in reversed(bars_rows)]
                payload = dict(candidate.payload_json or {})
                breadth = float(payload.get("breadth_score") or payload.get("context_score") or 50.0)
                result = self.engine.evaluate(candidate.symbol, bars, candidate_payload=payload,
                                              dealer_payload=self._dealer_payload(session, candidate.symbol),
                                              breadth_score=breadth, timeframe=timeframe)
                existing = session.execute(select(InflectionSnapshotModel).where(
                    InflectionSnapshotModel.publication_name == self.PUBLICATION,
                    InflectionSnapshotModel.source_run_id == source_run,
                    InflectionSnapshotModel.symbol == candidate.symbol,
                    InflectionSnapshotModel.timeframe == timeframe,
                )).scalars().first()
                model = existing or InflectionSnapshotModel(snapshot_id=f"M68-INF-{uuid4().hex.upper()}", publication_name=self.PUBLICATION,
                    source_run_id=source_run, symbol=candidate.symbol, timeframe=timeframe,
                    direction=result["direction"], transition_state=result["transition_state"], inflection_score=result["inflection_score"],
                    confidence=result["confidence"], horizon_min_sessions=result["horizon_min_sessions"], horizon_max_sessions=result["horizon_max_sessions"],
                    state_hash=result["state_hash"], snapshot_timestamp=published_at, payload_json={})
                for field in ("direction","transition_state","inflection_score","confidence","horizon_min_sessions","horizon_max_sessions","state_hash"):
                    setattr(model, field, result[field])
                model.snapshot_timestamp = published_at; model.payload_json = result
                if not existing: session.add(model)
                timeline = session.execute(select(InflectionTimelineEventModel).where(
                    InflectionTimelineEventModel.symbol == candidate.symbol,
                    InflectionTimelineEventModel.timeframe == timeframe,
                    InflectionTimelineEventModel.state_hash == result["state_hash"],
                )).scalars().first()
                if not timeline:
                    session.add(InflectionTimelineEventModel(event_id=f"M68-TL-{uuid4().hex.upper()}", symbol=candidate.symbol,
                        timeframe=timeframe, transition_state=result["transition_state"], inflection_score=result["inflection_score"],
                        confidence=result["confidence"], state_hash=result["state_hash"], event_timestamp=published_at, payload_json=result))
                payload["inflection_intelligence"] = result
                candidate.payload_json = payload
                for opp in session.execute(select(InstitutionalOpportunityModel).where(
                    InstitutionalOpportunityModel.stock_scanner_run_id == source_run,
                    InstitutionalOpportunityModel.symbol == candidate.symbol)).scalars().all():
                    op = dict(opp.payload_json or {}); op["inflection_intelligence"] = result; opp.payload_json = op
                    decision = session.execute(select(InstitutionalDecisionSnapshotModel).where(
                        InstitutionalDecisionSnapshotModel.opportunity_id == opp.opportunity_id)).scalars().first()
                    if decision:
                        dp = dict(decision.payload_json or {}); dp["inflection_intelligence"] = result; decision.payload_json = dp
                result["build_mode"] = build_mode
                result["lineage"] = {
                    "stock_scanner_run_id": source_run,
                    "build_mode": build_mode,
                    "dealer_input_available": bool(self._dealer_payload(session, candidate.symbol)),
                    "component_freshness": {"underlying": "CURRENT", "dealer_options": "CURRENT" if build_mode == "OPTIONS_ENRICHMENT" else "LATEST_AVAILABLE"},
                }
                model.payload_json = result
                built += 1; scores.append(result["inflection_score"])
                transitions[result["transition_state"]] = transitions.get(result["transition_state"], 0) + 1
                directions[result["direction"]] = directions.get(result["direction"], 0) + 1
                for name, value in result.get("components", {}).items():
                    if name in component_values: component_values[name].append(float(value))
                high += int(result["inflection_score"] >= 80)
            publication = session.execute(select(InflectionPublicationModel).where(InflectionPublicationModel.publication_name == self.PUBLICATION)).scalars().first()
            status = "READY" if built else "DEGRADED"
            diagnostics = self._diagnostics(scores, transitions, directions, component_values)
            summary = {"source_run_id": source_run, "built": built, "skipped": skipped, "high_conviction": high,
                       "average_score": round(sum(scores)/len(scores), 4) if scores else 0.0, "timeframe": timeframe,
                       "build_mode": build_mode, "diagnostics": diagnostics}
            if publication:
                publication.source_run_id=source_run; publication.status=status; publication.symbol_count=built; publication.high_conviction_count=high; publication.published_at=published_at; publication.payload_json=summary
            else:
                session.add(InflectionPublicationModel(publication_id=f"M68-PUB-{uuid4().hex.upper()}", publication_name=self.PUBLICATION,
                    source_run_id=source_run, status=status, symbol_count=built, high_conviction_count=high, published_at=published_at, payload_json=summary))
            session.commit()
            return {"status": status, **summary, "published_at": published_at}

    def current(self, *, limit: int = 100) -> dict:
        with self.session_factory() as session:
            pub = session.execute(select(InflectionPublicationModel).where(InflectionPublicationModel.publication_name == self.PUBLICATION)).scalars().first()
            rows = session.execute(select(InflectionSnapshotModel).where(
                InflectionSnapshotModel.publication_name == self.PUBLICATION,
                InflectionSnapshotModel.source_run_id == pub.source_run_id if pub else ""
            ).order_by(desc(InflectionSnapshotModel.inflection_score)).limit(limit)).scalars().all() if pub else []
            return {"publication": None if not pub else {"publication_id": pub.publication_id, "status": pub.status, "source_run_id": pub.source_run_id,
                    "symbol_count": pub.symbol_count, "high_conviction_count": pub.high_conviction_count, "published_at": pub.published_at, "payload": pub.payload_json},
                    "snapshots": [r.payload_json for r in rows]}
