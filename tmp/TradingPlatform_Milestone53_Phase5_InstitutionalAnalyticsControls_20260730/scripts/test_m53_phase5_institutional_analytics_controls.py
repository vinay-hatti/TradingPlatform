from pathlib import Path
import tempfile

from trading_ai.daily_scan_workstation.models import DailyScanRequest
from trading_ai.daily_scan_workstation.service import DailyScanWorkstationService


def main() -> None:
    request = DailyScanRequest(
        direction="bullish",
        minimum_trend_quality_score=70,
        minimum_transition_confirmation_score=60,
        maximum_exhaustion_risk_score=40,
        require_fresh_dealer_context=True,
        minimum_participation_score=65,
    )
    assert request.direction == "bullish"
    good = {
        "signal": "CALL",
        "trend_quality_score": 80,
        "trend_alignment_score": 75,
        "trend_confidence": 75,
        "transition_confirmation_score": 70,
        "reversal_risk_score": 20,
        "exhaustion_risk_score": 30,
        "dealer_context_status": "FRESH",
        "dealer_score_adjustment": 2,
        "market_structure_confidence": 70,
        "participation_score": 72,
        "leadership_score": 70,
        "institutional_conviction_score": 75,
        "deterioration_risk_score": 20,
        "breadth_confirmation_score": 70,
        "cross_asset_confirmation_score": 70,
    }
    bad = {**good, "signal": "PUT"}
    payload = request.model_dump(mode="json")
    assert DailyScanWorkstationService._passes_institutional_filters(good, payload)
    assert not DailyScanWorkstationService._passes_institutional_filters(bad, payload)
    filtered = DailyScanWorkstationService._filtered_payload({"trades": [good, bad]}, payload, "trades")
    assert len(filtered["trades"]) == 1
    assert filtered["metadata"]["pre_filter_count"] == 2
    assert filtered["metadata"]["post_filter_count"] == 1

    root = Path(__file__).resolve().parents[1]
    pages = (root / "ui/workstation/src/pages.tsx").read_text(encoding="utf-8")
    assert "Trend & transition intelligence" in pages
    assert "Dealer, institutional & market confirmation" in pages
    assert "minimum_trend_quality_score" in pages
    assert "minimum_participation_score" in pages
    assert "refresh_mode:persistedOnly?'cache_only'" in pages
    print("Milestone 53 Phase 5 institutional analytics control assertions passed.")


if __name__ == "__main__":
    main()
