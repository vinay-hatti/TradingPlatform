from __future__ import annotations

import argparse
from datetime import date
from uuid import uuid4

from trading_ai.research_workstation.scanner import (
    CandidateEnrichmentDefaults,
    HistoricalFeatureAdapter,
    MarketCandidateFactory,
    MarketScanRequestProfile,
    MarketScannerInputService,
    MarketScannerService,
    OptionHistoryDataAdapter,
    OptionsEnrichmentEngine,
    OptionsEnrichmentService,
    PriceHistoryMarketDataAdapter,
    ScannerFilterProfile,
    StaticMarketUniverseProvider,
)


def parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the institutional scanner from stored market history."
    )
    parser.add_argument("--universe", default="core_options")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--options-start")
    parser.add_argument("--options-end")
    parser.add_argument("--maximum-results", type=int, default=20)
    parser.add_argument("--min-option-volume", type=int, default=100)
    parser.add_argument("--min-open-interest", type=int, default=100)
    parser.add_argument("--max-spread-pct", type=float, default=0.20)
    parser.add_argument("--min-iv-rank", type=float, default=0.0)
    parser.add_argument(
        "--output",
        default="reports/scans/m34_phase1_step3_enriched_scan.json",
    )
    args = parser.parse_args()

    options_service = OptionsEnrichmentService(
        adapter=OptionHistoryDataAdapter(),
        engine=OptionsEnrichmentEngine(
            minimum_contract_volume=1,
            minimum_contract_open_interest=1,
            maximum_contract_spread_pct=args.max_spread_pct,
        ),
    )

    input_service = MarketScannerInputService(
        universe_provider=StaticMarketUniverseProvider(),
        market_data_adapter=PriceHistoryMarketDataAdapter(),
        feature_adapter=HistoricalFeatureAdapter(),
        candidate_factory=MarketCandidateFactory(
            CandidateEnrichmentDefaults(
                decision_confidence=50.0,
                expected_return=0.0,
                risk_score=50.0,
                reward_risk_ratio=0.0,
            )
        ),
        options_enrichment_service=options_service,
    )

    inputs = input_service.build_candidates(
        universe_name=args.universe,
        start=parse_date(args.start),
        end=parse_date(args.end),
        options_start=parse_date(args.options_start),
        options_end=parse_date(args.options_end),
    )

    request = MarketScanRequestProfile(
        scan_id=f"scan-{uuid4().hex[:12]}",
        universe=inputs.requested_symbols,
        filters=ScannerFilterProfile(
            min_price=5.0,
            min_average_volume=500_000,
            min_option_volume=args.min_option_volume,
            min_open_interest=args.min_open_interest,
            max_spread_pct=args.max_spread_pct,
            min_iv_rank=args.min_iv_rank,
            minimum_atr_pct=0.5,
            required_signals=("CALL", "PUT"),
        ),
        maximum_results=args.maximum_results,
        minimum_composite_score=30.0,
    )

    result = MarketScannerService().execute(
        request=request,
        candidates=list(inputs.candidates),
        output_path=args.output,
    )

    print("========== Enriched Institutional Scanner ==========")
    print(f"Universe       : {inputs.universe_name}")
    print(f"Requested      : {len(inputs.requested_symbols)}")
    print(f"Candidates     : {len(inputs.candidates)}")
    print(f"Skipped        : {len(inputs.skipped_symbols)}")
    print(f"Rejected       : {result.rejected_count}")
    print(f"Ranked Results : {len(result.ranked_candidates)}")
    print("----------------------------------------------------")
    for candidate in result.ranked_candidates:
        source = candidate.source
        print(
            f"{candidate.rank:>2}. {candidate.symbol:<6} "
            f"score={candidate.composite_score:>6.2f} "
            f"signal={candidate.signal:<5} "
            f"ivrank={source.iv_rank:>6.2f} "
            f"ivpct={source.iv_percentile:>6.2f} "
            f"optvol={source.option_volume:>8} "
            f"oi={source.open_interest:>8} "
            f"spread={source.spread_pct:>6.3f}"
        )
    if inputs.skipped_symbols:
        print(f"Skipped symbols: {', '.join(inputs.skipped_symbols)}")
    print(f"Report         : {args.output}")


if __name__ == "__main__":
    main()
