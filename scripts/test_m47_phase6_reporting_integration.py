from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.daily.models import DailyCandidate
from trading_ai.daily.reporter import DailyRecommendationReporter
from trading_ai.reporting import ReportingContext


def candidate() -> DailyCandidate:
    return DailyCandidate(
        symbol="AAPL", signal="CALL", strategy="LONG_CALL", close=225.0,
        score=70.0, call_score=70.0, put_score=20.0, market_regime="TREND_UP",
        strike=230.0, expiry="2026-08-21", option_price=3.25,
        delta=0.45, gamma=0.02, theta=-0.08, vega=0.15, rho=0.04,
        volatility=0.25, dte=27, final_score=70.0, ai_score=70.0,
        technical_score=72.0, greeks_score=68.0, regime_score=75.0,
        volatility_score=65.0, risk_score=70.0, adjusted_score=70.0,
        ranking_reason="phase6 test", publication_name="current_market_state",
        ingestion_run_id="readiness-test", publication_status="DEGRADED",
        published_at="2026-07-25T23:52:16Z", market_as_of_date="2026-07-23",
        market_intelligence_snapshot_timestamp="2026-07-25T23:49:40Z",
        option_snapshot_timestamp="2026-07-25T17:45:07Z",
        option_snapshot_id="polygon-test", option_snapshot_completeness_pct=99.5,
        published_state_degraded=True, scanner_run_id="scanner-test",
        candidate_id="cand-test", market_state_hash="hash-test",
        scanner_version="m47.phase6.v1",
    )


def main() -> None:
    metadata = {
        "date": "2026-07-25",
        "symbols_scanned": 1,
        "live_profile": "aggressive",
        "min_score": 60,
        "pricing_dte": 30,
        "scanner_run_id": "scanner-test",
        "scanner_version": "m47.phase6.v1",
        "published_state": {
            "publication_name": "current_market_state",
            "publication_status": "DEGRADED",
            "ingestion_run_id": "readiness-test",
            "published_at": "2026-07-25T23:52:16Z",
            "market_as_of_date": "2026-07-23",
            "option_snapshot_id": "polygon-test",
            "option_snapshot_timestamp": "2026-07-25T17:45:07Z",
            "market_intelligence_snapshot_timestamp": "2026-07-25T23:49:40Z",
            "option_snapshot_completeness_pct": 99.5,
            "published_state_degraded": True,
        },
    }
    context = ReportingContext.from_metadata(metadata)
    assert context.scanner_run_id == "scanner-test"
    assert context.publication_name == "current_market_state"
    assert context.market_state_hash

    with TemporaryDirectory() as tmp:
        reporter = DailyRecommendationReporter(base_dir=tmp)
        paths = reporter.generate([candidate()], metadata, {"positions": 0}, "2026-07-25")
        for key in ("csv", "json", "html", "manifest"):
            assert Path(paths[key]).exists(), key

        payload = json.loads(Path(paths["json"]).read_text())
        assert payload["report_version"] == "m47.phase6.v1"
        assert payload["reporting_context"]["scanner_run_id"] == "scanner-test"
        assert payload["candidates"][0]["candidate_id"] == "cand-test"

        with Path(paths["csv"]).open(newline="") as handle:
            row = next(csv.DictReader(handle))
        assert row["scanner_run_id"] == "scanner-test"
        assert row["candidate_id"] == "cand-test"
        assert row["market_state_hash"] == "hash-test"

        html = Path(paths["html"]).read_text()
        assert "Published Market State" in html
        assert "Governance Summary" in html
        assert "scanner-test" in html
        assert "polygon-test" in html

        manifest = json.loads(Path(paths["manifest"]).read_text())
        assert manifest["report_type"] == "daily_recommendations"
        assert len(manifest["artifacts"]) == 3
        assert all(item["sha256"] for item in manifest["artifacts"])

    print("Milestone 47 Phase 6 reporting-integration assertions passed.")


if __name__ == "__main__":
    main()
