from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class SymbolPopulationResult:
    symbol: str
    status: str
    rows_received: int = 0
    rows_upserted: int = 0
    attempts: int = 1
    message: str = ""
    failure_category: str = ""
    first_date: date | None = None
    last_date: date | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketDataCoverage:
    universe_symbols: int
    covered_symbols: int
    stale_symbols: int
    insufficient_symbols: int
    missing_symbols: int
    coverage_pct: float
    minimum_required_pct: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketDataPopulationResult:
    run_id: str
    started_at: datetime
    completed_at: datetime
    status: str
    requested_symbols: int
    attempted_symbols: int
    succeeded_symbols: int
    failed_symbols: int
    skipped_fresh_symbols: int
    rows_upserted: int
    coverage: MarketDataCoverage
    results: tuple[SymbolPopulationResult, ...] = ()
    warnings: tuple[str, ...] = ()
    error: str = ""
    checkpoint_path: str = ""
    report_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["coverage"] = self.coverage.to_dict()
        payload["results"] = [item.to_dict() for item in self.results]
        return payload
