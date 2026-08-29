from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import tempfile

from trading_ai.daily.models import DailyCandidate
from trading_ai.daily.published_context import ScannerPublishedStateContext
from trading_ai.daily.recommender import LiveTradeRecommender
from trading_ai.published_state.profile import PublishedMarketState

state = PublishedMarketState(
    publication_name="current_market_state", run_id="run-47",
    published_at=datetime.now(timezone.utc), as_of_date=date(2026,7,23),
    market_intelligence_timestamp=datetime.now(timezone.utc),
    option_snapshot_timestamp=datetime.now(timezone.utc), option_snapshot_id="polygon-snapshot",
    readiness_status="DEGRADED", scanner_ready=True, decision_context_ready=True,
    details={"checks":[{"name":"option_snapshot_completeness","latest_value":"99.5"}]},
    age_seconds=1.0, degraded=True,
)
ctx = ScannerPublishedStateContext.from_state(state)
assert ctx.option_snapshot_completeness_pct == 99.5
fields = ctx.candidate_fields()
assert fields["ingestion_run_id"] == "run-47"
assert fields["published_state_degraded"] is True

required = dict(symbol="AAPL", signal="CALL", strategy="LONG_CALL", close=200.0, score=80.0,
 call_score=80.0, put_score=10.0, market_regime="BULL_TREND", strike=205.0, expiry="2026-08-21",
 option_price=2.0, delta=.45, gamma=.1, theta=-.02, vega=.1, rho=0.0, volatility=.2, dte=27, final_score=80.0)
candidate = DailyCandidate(**required, **fields)
trade = LiveTradeRecommender().build(candidate)
assert trade.option_snapshot_id == "polygon-snapshot"
assert trade.ingestion_run_id == "run-47"
assert trade.publication_status == "DEGRADED"
print("Milestone 47 Phase 2 daily-scanner published-state assertions passed.")
