from pathlib import Path
from uuid import uuid4

from trading_ai.research_workstation.scanner import (
    HistoricalFeatureAdapter,
    MarketCandidateFactory,
    MarketScanRequestProfile,
    MarketScannerInputService,
    MarketScannerService,
    OptionsEnrichmentEngine,
    OptionsEnrichmentService,
    PriceHistoryMarketDataAdapter,
    RepositoryOptionsDataAdapter,
    ScannerFilterProfile,
    StaticMarketUniverseProvider,
)
from trading_ai.ui.models.research_scanner import (
    ResearchScannerCandidate,
    ResearchScannerRequest,
    ResearchScannerResponse,
)


class ResearchScannerDashboardService:
    def __init__(
        self,
        input_service=None,
        scanner_service=None,
        report_directory="reports/scans",
    ):
        if input_service is None:
            input_service = MarketScannerInputService(
                universe_provider=StaticMarketUniverseProvider(),
                market_data_adapter=PriceHistoryMarketDataAdapter(),
                feature_adapter=HistoricalFeatureAdapter(),
                candidate_factory=MarketCandidateFactory(),
                options_enrichment_service=OptionsEnrichmentService(
                    adapter=RepositoryOptionsDataAdapter(),
                    engine=OptionsEnrichmentEngine(),
                ),
            )

        self.input_service = input_service
        self.scanner_service = scanner_service or MarketScannerService()
        self.report_directory = Path(report_directory)

    def execute(
        self,
        request: ResearchScannerRequest,
    ) -> ResearchScannerResponse:
        inputs = self.input_service.build_candidates(
            universe_name=request.universe,
        )

        scan_id = f"research-{uuid4().hex[:12]}"
        report_path = self.report_directory / f"{scan_id}.json"

        scan_request = MarketScanRequestProfile(
            scan_id=scan_id,
            universe=inputs.requested_symbols,
            filters=ScannerFilterProfile(
                min_price=5.0,
                min_average_volume=request.minimum_average_volume,
                min_option_volume=request.minimum_option_volume,
                min_open_interest=request.minimum_open_interest,
                max_spread_pct=request.maximum_spread_pct,
                min_iv_rank=request.minimum_iv_rank,
                minimum_atr_pct=request.minimum_atr_pct,
                required_signals=tuple(
                    signal.upper()
                    for signal in request.required_signals
                ),
            ),
            maximum_results=request.maximum_results,
            minimum_composite_score=0.0,
        )

        result = self.scanner_service.execute(
            request=scan_request,
            candidates=list(inputs.candidates),
            output_path=str(report_path),
        )

        rows = []
        for ranked in result.ranked_candidates:
            item = ranked.source
            rows.append(
                ResearchScannerCandidate(
                    rank=ranked.rank,
                    symbol=ranked.symbol,
                    composite_score=ranked.composite_score,
                    signal=item.signal,
                    regime=item.regime,
                    price=item.price,
                    option_volume=item.option_volume,
                    open_interest=item.open_interest,
                    spread_pct=item.spread_pct,
                    iv_rank=item.iv_rank,
                    iv_percentile=item.iv_percentile,
                    decision_confidence=item.decision_confidence,
                    expected_return=item.expected_return,
                    risk_score=item.risk_score,
                    reward_risk_ratio=item.reward_risk_ratio,
                    institutional=dict(
                        item.metadata.get(
                            "institutional_decision",
                            {},
                        )
                    ),
                )
            )

        warnings = []
        if not inputs.candidates:
            warnings.append(
                "No candidates were produced from stored price history."
            )
        elif not rows:
            warnings.append(
                "No candidates passed the configured filters."
            )

        return ResearchScannerResponse(
            scan_id=scan_id,
            universe=inputs.universe_name,
            requested_count=len(inputs.requested_symbols),
            candidate_count=len(inputs.candidates),
            rejected_count=result.rejected_count,
            skipped_symbols=list(inputs.skipped_symbols),
            results=rows,
            report_path=str(report_path),
            warnings=warnings,
        )
