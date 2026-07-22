from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Protocol

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .contracts import UniverseCoverageProfile
from .freshness import MarketDataFreshnessEngine, UniverseFreshnessProfile
from .policy import MarketDataCoveragePolicy
from .repository import PriceHistoryCoverageRepository
from .serialization import (
    write_coverage_json,
    write_freshness_json,
    write_symbol_coverage_csv,
    write_symbol_freshness_csv,
)


class CanonicalSymbolSource(Protocol):
    def symbols(self) -> Iterable[str]: ...


@dataclass(frozen=True, slots=True)
class CoverageReportPaths:
    json_path: Path
    symbol_csv_path: Path


@dataclass(frozen=True, slots=True)
class FreshnessReportPaths:
    json_path: Path
    symbol_csv_path: Path


class MarketDataCoverageService:
    """Build canonical-universe coverage and freshness profiles from price_history."""

    def __init__(
        self,
        bind: Engine | Session,
        *,
        canonical_source: CanonicalSymbolSource | None = None,
        policy: MarketDataCoveragePolicy | None = None,
        repository: PriceHistoryCoverageRepository | None = None,
        freshness_engine: MarketDataFreshnessEngine | None = None,
        canonical_path: str | Path = "data/universe/us_listed_equities_etfs.csv",
    ) -> None:
        self.bind = bind
        self.policy = policy or MarketDataCoveragePolicy()
        self.canonical_source = canonical_source or _default_canonical_source(canonical_path)
        self.repository = repository or PriceHistoryCoverageRepository(bind)
        self.freshness_engine = freshness_engine or MarketDataFreshnessEngine()

    def evaluate(self) -> UniverseCoverageProfile:
        symbols = self._canonical_symbols()
        aggregate = self.repository.aggregate(symbols)
        profiles = []
        for symbol in symbols:
            record = aggregate.get(symbol)
            profiles.append(self.policy.build_symbol_profile(
                symbol=symbol,
                row_count=record.row_count if record else 0,
                trading_day_count=record.trading_day_count if record else 0,
                earliest_date=record.earliest_date if record else None,
                latest_date=record.latest_date if record else None,
            ))
        return self.policy.evaluate(profiles)

    def evaluate_freshness(self, *, as_of_date: date | None = None) -> UniverseFreshnessProfile:
        return self.freshness_engine.evaluate(self.evaluate(), as_of_date=as_of_date)

    def evaluate_and_write(self, output_directory: str | Path, *, json_filename: str = "market_data_coverage.json", symbol_csv_filename: str = "market_data_symbol_coverage.csv") -> tuple[UniverseCoverageProfile, CoverageReportPaths]:
        profile = self.evaluate()
        root = Path(output_directory)
        paths = CoverageReportPaths(
            json_path=write_coverage_json(profile, root / json_filename),
            symbol_csv_path=write_symbol_coverage_csv(profile, root / symbol_csv_filename),
        )
        return profile, paths

    def evaluate_freshness_and_write(self, output_directory: str | Path, *, as_of_date: date | None = None, json_filename: str = "market_data_freshness.json", symbol_csv_filename: str = "market_data_symbol_freshness.csv") -> tuple[UniverseFreshnessProfile, FreshnessReportPaths]:
        profile = self.evaluate_freshness(as_of_date=as_of_date)
        root = Path(output_directory)
        paths = FreshnessReportPaths(
            json_path=write_freshness_json(profile, root / json_filename),
            symbol_csv_path=write_symbol_freshness_csv(profile, root / symbol_csv_filename),
        )
        return profile, paths

    def _canonical_symbols(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            str(symbol or "").strip().upper()
            for symbol in self.canonical_source.symbols()
            if str(symbol or "").strip()
        ))


def _default_canonical_source(path: str | Path) -> CanonicalSymbolSource:
    try:
        from trading_ai.universe.canonical import CanonicalUniverse
    except ImportError as exc:
        raise ImportError("CanonicalUniverse is required before Phase 2 Step 3.") from exc
    return CanonicalUniverse(Path(path))
