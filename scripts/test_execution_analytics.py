from datetime import datetime, timedelta
import json

from trading_ai.strategy_engine.execution_analytics_policy import ExecutionAnalyticsPolicy
from trading_ai.strategy_engine.execution_analytics_profile import ExecutionFill
from trading_ai.strategy_engine.execution_analytics_service import ExecutionAnalyticsService
from trading_ai.strategy_engine.execution_analytics_serialization import execution_analytics_to_dict


def main():
    start = datetime(2026, 7, 13, 10, 0, 0)
    fills = [
        ExecutionFill(order_id="O1", symbol="AAPL", side="BUY", quantity_requested=10, quantity_filled=6, decision_price=5.00, arrival_price=5.02, fill_price=5.04, bid=4.98, ask=5.06, submitted_at=start, filled_at=start + timedelta(seconds=12), commission=3.0),
        ExecutionFill(order_id="O1", symbol="AAPL", side="BUY", quantity_requested=0, quantity_filled=4, decision_price=5.00, arrival_price=5.02, fill_price=5.05, bid=4.99, ask=5.07, submitted_at=start, filled_at=start + timedelta(seconds=20), commission=2.0),
    ]
    service = ExecutionAnalyticsService(ExecutionAnalyticsPolicy())
    profile = service.analyze(fills, symbol="AAPL", strategy="BULL_CALL_SPREAD")
    assert profile.valid is True
    assert profile.allowed is True
    assert profile.order_count == 2
    assert profile.filled_quantity == 10
    assert profile.fill_ratio == 1.0
    assert profile.implementation_shortfall_bps > 0
    assert 0 <= profile.execution_score <= 100
    assert profile.execution_grade in {"A", "B", "C", "D", "F"}
    assert profile.execution_severity in {"LOW", "MODERATE", "SEVERE", "CRITICAL"}
    payload = execution_analytics_to_dict(profile)
    json.dumps(payload)
    assert len(payload["fills"]) == 2

    estimate = service.estimate(symbol="MSFT", strategy="BULL_PUT_SPREAD", side="SELL", quantity=2, decision_price=2.0, bid=1.90, ask=2.10)
    assert estimate.valid is True
    assert estimate.metadata["midpoint"] == 2.0

    empty = service.analyze([], symbol="EMPTY")
    assert empty.valid is False
    assert "NO_EXECUTION_FILLS" in empty.warnings

    strict = ExecutionAnalyticsService(ExecutionAnalyticsPolicy(reject_critical_execution=True, critical_slippage_bps=50.0))
    critical = strict.analyze([ExecutionFill(symbol="TSLA", side="BUY", quantity_requested=1, quantity_filled=1, decision_price=10.0, arrival_price=10.0, fill_price=11.0, bid=9.9, ask=10.1)])
    assert critical.execution_severity == "CRITICAL"
    assert critical.allowed is False

    print("All execution-analytics assertions passed.")


if __name__ == "__main__":
    main()
