from __future__ import annotations

import json

from trading_ai.market_intelligence.service import MarketIntelligenceService
from trading_ai.persistence_normalization import strict_json_dumps


def main() -> None:
    snapshot = MarketIntelligenceService().build(persist=True)
    result = {
        "status": "READY",
        "snapshot_timestamp": snapshot.snapshot_timestamp,
        "as_of_date": snapshot.as_of_date,
        "correlation_regime": snapshot.correlation.get("regime"),
        "sentiment_label": snapshot.sentiment.get("sentiment_label"),
        "risk_regime": snapshot.risk.get("risk_regime"),
        "confidence": snapshot.scanner_context.get("confidence"),
    }
    print(strict_json_dumps(result, indent=2))


if __name__ == "__main__":
    main()
