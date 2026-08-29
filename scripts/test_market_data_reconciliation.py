from datetime import datetime, timedelta, timezone
from trading_ai.market.market_data_reconciliation_engine import MarketDataReconciliationEngine
from trading_ai.market.market_data_reconciliation_policy import MarketDataReconciliationPolicy
from trading_ai.market.market_data_reconciliation_serialization import dumps

def main():
    now = datetime.now(timezone.utc)
    engine = MarketDataReconciliationEngine(MarketDataReconciliationPolicy(
        maximum_price_difference_pct=0.02,
        warning_price_difference_pct=0.005,
        maximum_volume_difference_pct=0.25,
        warning_volume_difference_pct=0.10,
        maximum_timestamp_difference_seconds=120,
    ))
    ok = engine.evaluate(
        {"symbol":"AAPL","timestamp":now,"price":200.5,"volume":1100},
        {"symbol":"AAPL","timestamp":now-timedelta(seconds=30),"price":200.0,"volume":1000},
    )
    assert ok.allowed and ok.recommendation == "ACCEPT"
    warn = engine.evaluate(
        {"symbol":"MSFT","timestamp":now,"price":505,"volume":1150},
        {"symbol":"MSFT","timestamp":now,"price":500,"volume":1000},
    )
    assert warn.allowed and "PRICE_DIFFERENCE_WARNING" in warn.warnings
    bad = engine.evaluate(
        {"symbol":"AMZN","timestamp":now,"price":220,"volume":2000},
        {"symbol":"AMZN","timestamp":now-timedelta(seconds=300),"price":200,"volume":1000},
    )
    assert not bad.allowed
    assert "PRICE_DIFFERENCE" in bad.rejection_reasons
    summary = engine.evaluate_many((
        ({"symbol":"AAPL","timestamp":now,"price":200.5,"volume":1100},{"symbol":"AAPL","timestamp":now,"price":200,"volume":1000}),
        ({"symbol":"AMZN","timestamp":now,"price":220,"volume":2000},{"symbol":"AMZN","timestamp":now,"price":200,"volume":1000}),
    ))
    assert summary.total_count == 2 and summary.matched_count == 1 and summary.rejected_count == 1
    assert '"total_count": 2' in dumps(summary)
    print("All live/historical market-data reconciliation assertions passed.")
if __name__ == "__main__": main()
