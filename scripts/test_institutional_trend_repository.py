from __future__ import annotations
from datetime import datetime, timezone
from trading_ai.trend_intelligence.institutional_contracts import InstitutionalTrendSnapshot
from trading_ai.trend_intelligence.institutional_repository import InstitutionalTrendRepository

s = InstitutionalTrendSnapshot(
 symbol="M52P4TEST", as_of_date="2026-07-28", snapshot_timestamp=datetime.now(timezone.utc),
 participation_score=60, participation_grade="C", participation_confidence=75,
 institutional_conviction_score=61, relative_volume_20d=1.2, volume_trend_score=62,
 volume_thrust_score=64, price_volume_confirmation_score=60, accumulation_distribution_score=59,
 distribution_risk_score=32, leadership_score=66, leadership_grade="B",
 market_relative_strength_20d=2, market_relative_strength_60d=4, leadership_persistence_score=70,
 breadth_confirmation_score=50, cross_asset_confirmation_score=50, trend_quality_score=62,
 deterioration_risk_score=31, participation_state="MIXED", leadership_state="LEADER", deterioration_state="STABLE")
r = InstitutionalTrendRepository(); r.save(s); p = r.latest("M52P4TEST")
assert p and p["symbol"] == "M52P4TEST"
assert r.scanner_context("M52P4TEST", reference_date="2026-07-28")["institutional_context_status"] == "FRESH"
print("All Institutional Trend repository assertions passed.")
