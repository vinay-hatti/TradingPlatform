from __future__ import annotations

from dataclasses import replace
from datetime import date

from .market_scanner_profile import MarketCandidateProfile
from .options_data_adapter import OptionsDataAdapter
from .options_enrichment_engine import OptionsEnrichmentEngine


class OptionsEnrichmentService:
    def __init__(
        self,
        *,
        adapter: OptionsDataAdapter,
        engine: OptionsEnrichmentEngine | None = None,
    ):
        self.adapter = adapter
        self.engine = engine or OptionsEnrichmentEngine()

    def enrich(
        self,
        candidates: tuple[MarketCandidateProfile, ...] | list[MarketCandidateProfile],
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> tuple[MarketCandidateProfile, ...]:
        symbols = tuple(candidate.symbol for candidate in candidates)
        contracts_by_symbol = self.adapter.load_contracts(
            symbols=symbols,
            start=start,
            end=end,
        )

        enriched: list[MarketCandidateProfile] = []

        for candidate in candidates:
            snapshot = self.engine.build_snapshot(
                candidate.symbol,
                contracts_by_symbol.get(candidate.symbol, ()),
            )

            if snapshot is None:
                enriched.append(candidate)
                continue

            metadata = dict(candidate.metadata)
            metadata.update(
                {
                    "options_quote_date": snapshot.quote_date.isoformat(),
                    "options_contract_count": snapshot.contract_count,
                    "options_liquid_contract_count": snapshot.liquid_contract_count,
                }
            )

            enriched.append(
                replace(
                    candidate,
                    option_volume=snapshot.option_volume,
                    open_interest=snapshot.open_interest,
                    spread_pct=snapshot.median_spread_pct,
                    iv_rank=snapshot.iv_rank,
                    iv_percentile=snapshot.iv_percentile,
                    metadata=metadata,
                )
            )

        return tuple(enriched)
