from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .market_candidate_factory import MarketCandidateFactory
from .market_data_adapter import MarketDataAdapter
from .market_feature_adapter import MarketFeatureAdapter
from .market_scanner_profile import MarketCandidateProfile
from .market_universe import MarketUniverseProvider
from .options_enrichment_service import OptionsEnrichmentService


@dataclass(frozen=True)
class MarketScannerInputResult:
    universe_name: str
    requested_symbols: tuple[str, ...]
    candidates: tuple[MarketCandidateProfile, ...]
    skipped_symbols: tuple[str, ...]


class MarketScannerInputService:
    def __init__(
        self,
        *,
        universe_provider: MarketUniverseProvider,
        market_data_adapter: MarketDataAdapter,
        feature_adapter: MarketFeatureAdapter,
        candidate_factory: MarketCandidateFactory | None = None,
        options_enrichment_service: OptionsEnrichmentService | None = None,
    ):
        self.universe_provider = universe_provider
        self.market_data_adapter = market_data_adapter
        self.feature_adapter = feature_adapter
        self.candidate_factory = candidate_factory or MarketCandidateFactory()
        self.options_enrichment_service = options_enrichment_service

    def build_candidates(
        self,
        *,
        universe_name: str,
        start: date | None = None,
        end: date | None = None,
        options_start: date | None = None,
        options_end: date | None = None,
    ) -> MarketScannerInputResult:
        universe = self.universe_provider.load(universe_name)
        symbols = universe.normalized_symbols()
        bars_by_symbol = self.market_data_adapter.load_bars(
            symbols=symbols,
            start=start,
            end=end,
        )

        candidates: list[MarketCandidateProfile] = []
        skipped: list[str] = []

        for symbol in symbols:
            snapshot = self.feature_adapter.build(
                symbol,
                bars_by_symbol.get(symbol, ()),
            )
            if snapshot is None:
                skipped.append(symbol)
                continue
            candidates.append(self.candidate_factory.from_feature_snapshot(snapshot))

        candidate_tuple = tuple(candidates)

        if self.options_enrichment_service is not None and candidate_tuple:
            candidate_tuple = self.options_enrichment_service.enrich(
                candidate_tuple,
                start=options_start,
                end=options_end,
            )

        return MarketScannerInputResult(
            universe_name=universe.name,
            requested_symbols=symbols,
            candidates=candidate_tuple,
            skipped_symbols=tuple(skipped),
        )
