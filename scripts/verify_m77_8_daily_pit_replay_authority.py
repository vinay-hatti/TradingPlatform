#!/usr/bin/env python3
from pathlib import Path
import inspect

from trading_ai.historical_underlying_replay.regime import (
    HistoricalRegimeAuthorityService,
    REGIME_AUTHORITY_VERSION,
)
from trading_ai.market.providers.polygon import PolygonHistoricalProvider


assert REGIME_AUTHORITY_VERSION == "M77.3-HISTORICAL-REGIME-AUTHORITY-1.0"

regime_source = inspect.getsource(HistoricalRegimeAuthorityService)
assert "WHERE date <= :end" in regime_source
assert "_trend_state" in regime_source
assert "_volatility_state" in regime_source
assert "_breadth_state" in regime_source

# Verify method existence structurally, rather than searching a whitespace-normalized
# source string for tokens that themselves contain whitespace.
assert hasattr(PolygonHistoricalProvider, "fetch_history")
assert callable(getattr(PolygonHistoricalProvider, "fetch_history"))
assert hasattr(PolygonHistoricalProvider, "fetch_grouped_daily")
assert callable(getattr(PolygonHistoricalProvider, "fetch_grouped_daily"))

polygon_source = inspect.getsource(PolygonHistoricalProvider)
polygon_compact = "".join(polygon_source.split())
assert polygon_compact.count("adjusted=True") >= 2

runner = Path(
    "scripts/run_m77_8_daily_pit_replay_authority.py"
).read_text()

assert "from trading_ai.database.session import SessionLocal" in runner
assert "DATABASE_URL" not in runner
assert '"database_writes": False' in runner
assert '"production_authority_effect": False' in runner
assert '"existing_weekly_m77_mutation": False' in runner
assert "DAILY_HORIZONS = (5, 10, 20, 40, 60)" in runner
assert "compare_snapshot" in runner

print("M77.8.1 source verification PASSED")
print(" - installed M77.3 PIT regime authority preserved")
print(" - Polygon provider method presence verified structurally")
print(" - Polygon adjusted=True semantics verified independently of whitespace")
print(" - SessionLocal database convention preserved")
print(" - daily authority remains read-only and additive")
