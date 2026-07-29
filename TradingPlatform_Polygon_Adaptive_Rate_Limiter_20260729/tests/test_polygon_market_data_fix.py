from datetime import datetime, timezone
import pandas as pd
from trading_ai.market.service import MarketService

def test_polygon_frame_normalizes_for_price_history():
    timestamp = int(datetime(2026, 7, 28, tzinfo=timezone.utc).timestamp() * 1000)
    frame = pd.DataFrame([{"symbol":"AAPL","time":timestamp,"open":10,"high":12,"low":9,"close":11,"volume":100}])
    rows = MarketService._persistence_rows(frame)
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["date"].isoformat() == "2026-07-28"
    assert rows[0]["close"] == 11.0

def test_multi_session_stale_cache_is_rejected():
    timestamp = int(datetime(2026, 7, 24, tzinfo=timezone.utc).timestamp() * 1000)
    frame = pd.DataFrame([{"symbol":"AAPL","time":timestamp,"open":10,"high":12,"low":9,"close":11,"volume":100}])
    assert MarketService._cache_is_fresh(frame, "2026-07-29") is False
