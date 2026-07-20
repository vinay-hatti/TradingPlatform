from __future__ import annotations

import json
from pathlib import Path

from .market_scanner_profile import MarketScanResultProfile


def serialize_market_scan_result(result: MarketScanResultProfile) -> dict:
    return result.to_dict()


def write_market_scan_result(
    result: MarketScanResultProfile,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(serialize_market_scan_result(result), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path
