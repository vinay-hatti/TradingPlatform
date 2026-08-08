from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

from sqlalchemy import select, text

from trading_ai.market.models import PriceHistory

from .context_loader import PersistedStockContextLoader
from .orchestration import StockScannerOrchestrator


@dataclass(frozen=True)
class StockPublicationRequest:
    symbols: tuple[str, ...]
    publication_name: str = "current_stock_intelligence"
    minimum_score: float = 0.0
    top: int | None = None
    lookback_days: int = 750
    snapshot_timestamp: str | None = None
    ingestion_run_id: str | None = None
    market_publication_name: str = "current_market_state"


class StockIntelligencePublicationService:
    """Publish governed Stock Intelligence from persisted Polygon-backed state.

    The service is shared by the standalone scanner command and the authoritative
    market-ingestion workflow. It never downloads data itself.
    """

    def __init__(self, session):
        self.session = session

    @staticmethod
    def normalize_symbols(values: Iterable[str]) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            symbol = str(value or "").strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            result.append(symbol)
        if not result:
            raise ValueError("At least one symbol is required for Stock Intelligence publication")
        return tuple(result)

    @staticmethod
    def _row(record: PriceHistory) -> dict:
        return {
            "date": record.date.isoformat(),
            "open": float(record.open or 0),
            "high": float(record.high or 0),
            "low": float(record.low or 0),
            "close": float(record.close or 0),
            "volume": float(record.volume or 0),
        }

    @staticmethod
    def _aggregate(rows: list[dict], period: str) -> list[dict]:
        buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)
        for item in rows:
            dt = date.fromisoformat(str(item["date"])[:10])
            if period == "week":
                iso = dt.isocalendar()
                key = (iso.year, iso.week)
            elif period == "month":
                key = (dt.year, dt.month)
            else:
                raise ValueError(f"Unsupported aggregation period: {period}")
            buckets[key].append(item)
        values: list[dict] = []
        for key in sorted(buckets):
            group = sorted(buckets[key], key=lambda value: value["date"])
            values.append(
                {
                    "date": group[-1]["date"],
                    "open": group[0]["open"],
                    "high": max(value["high"] for value in group),
                    "low": min(value["low"] for value in group),
                    "close": group[-1]["close"],
                    "volume": sum(value["volume"] for value in group),
                }
            )
        return values

    def _market_lineage(self, publication_name: str) -> dict:
        row = self.session.execute(
            text(
                """
                SELECT publication_name, run_id, published_at, as_of_date,
                       market_intelligence_timestamp, option_snapshot_timestamp,
                       option_snapshot_id, readiness_status, scanner_ready
                  FROM market_ingestion_publication
                 WHERE publication_name = :name
                 LIMIT 1
                """
            ),
            {"name": publication_name},
        ).mappings().one_or_none()
        return dict(row) if row else {}

    def publish(self, request: StockPublicationRequest) -> dict:
        symbols = self.normalize_symbols(request.symbols)
        snapshot = request.snapshot_timestamp or datetime.now(timezone.utc).isoformat()
        data_by_symbol: dict[str, dict[str, list[dict]]] = {}
        external_context_by_symbol: dict[str, dict] = {}
        context_loader = PersistedStockContextLoader(self.session)

        for symbol in symbols:
            records = list(
                self.session.scalars(
                    select(PriceHistory)
                    .where(PriceHistory.symbol == symbol)
                    .order_by(PriceHistory.date.desc())
                    .limit(max(100, int(request.lookback_days)))
                )
            )
            rows = [self._row(record) for record in reversed(records)]
            if not rows:
                continue
            data_by_symbol[symbol] = {
                "1d": rows,
                "1w": self._aggregate(rows, "week"),
                "1mo": self._aggregate(rows, "month"),
            }
            external_context_by_symbol[symbol] = context_loader.for_symbol(symbol)

        if not data_by_symbol:
            raise RuntimeError("No persisted Polygon price_history rows were available for requested symbols")

        lineage = self._market_lineage(request.market_publication_name)
        result = StockScannerOrchestrator(self.session).run(
            data_by_symbol,
            external_context_by_symbol=external_context_by_symbol,
            publication_name=request.publication_name,
            minimum_score=request.minimum_score,
            top=request.top,
            snapshot_timestamp=snapshot,
            lineage={
                "ingestion_run_id": request.ingestion_run_id,
                "market_publication_name": request.market_publication_name,
                "market_publication_run_id": lineage.get("run_id"),
                "market_publication_status": lineage.get("readiness_status"),
                "market_as_of_date": str(lineage.get("as_of_date") or "") or None,
                "market_snapshot_timestamp": str(lineage.get("market_intelligence_timestamp") or "") or None,
                "option_snapshot_id": lineage.get("option_snapshot_id"),
                "option_snapshot_timestamp": str(lineage.get("option_snapshot_timestamp") or "") or None,
                "publisher": "run_market_ingestion.py" if request.ingestion_run_id else "run_m61_stock_intelligence_scanner.py",
            },
        )
        result.update(
            {
                "symbols_requested": len(symbols),
                "symbols_analyzed": len(data_by_symbol),
                "symbols_missing_price_history": len(symbols) - len(data_by_symbol),
                "timeframes": ["1d", "1w", "1mo"],
                "source": "POLYGON_PERSISTED",
                "market_publication_name": request.market_publication_name,
                "ingestion_run_id": request.ingestion_run_id,
            }
        )
        return result
