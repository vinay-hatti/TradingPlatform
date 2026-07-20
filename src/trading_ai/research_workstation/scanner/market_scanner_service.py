from __future__ import annotations

from pathlib import Path

from .market_scanner_engine import MarketScannerEngine
from .market_scanner_profile import (
    MarketCandidateProfile,
    MarketScanRequestProfile,
    MarketScanResultProfile,
)
from .market_scanner_serialization import write_market_scan_result


class MarketScannerService:
    def __init__(self, engine: MarketScannerEngine | None = None):
        self.engine = engine or MarketScannerEngine()

    def execute(
        self,
        request: MarketScanRequestProfile,
        candidates: list[MarketCandidateProfile],
        *,
        output_path: str | Path | None = None,
    ) -> MarketScanResultProfile:
        result = self.engine.scan(request=request, candidates=candidates)
        if output_path is not None:
            write_market_scan_result(result, output_path)
        return result
