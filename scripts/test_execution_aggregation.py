from datetime import datetime, timedelta
import json

from trading_ai.strategy_engine.execution_aggregation_service import ExecutionAggregationService
from trading_ai.strategy_engine.execution_aggregation_serialization import execution_aggregation_to_dict
from trading_ai.strategy_engine.execution_analytics_profile import ExecutionFill


def build_fills():
    start = datetime(2026, 7, 13, 14, 30)
    rows = []
    specifications = [
        ("O1", "AAPL", "BUY", 2, 2, 5.00, 5.02, 5.04, 4.99, 5.05, "CBOE", "BROKER_A", 4),
        ("O2", "MSFT", "SELL", 3, 3, 4.00, 3.99, 3.98, 3.95, 4.03, "ISE", "BROKER_B", 8),
        ("O3", "JPM", "BUY", 4, 3, 2.50, 2.52, 2.56, 2.48, 2.57, "CBOE", "BROKER_A", 12),
        ("O3", "JPM", "BUY", 4, 1, 2.50, 2.52, 2.59, 2.48, 2.60, "CBOE", "BROKER_A", 16),
        ("O4", "NVDA", "SELL", 2, 2, 6.00, 5.98, 5.94, 5.92, 6.02, "BOX", "BROKER_C", 24),
        ("O5", "AMZN", "BUY", 1, 1, 3.00, 3.01, 3.03, 2.98, 3.04, "ISE", "BROKER_B", 6),
    ]
    for i, spec in enumerate(specifications):
        order, symbol, side, requested, filled, decision, arrival, price, bid, ask, venue, broker, delay = spec
        rows.append(ExecutionFill(
            order_id=order,
            symbol=symbol,
            side=side,
            quantity_requested=requested,
            quantity_filled=filled,
            decision_price=decision,
            arrival_price=arrival,
            fill_price=price,
            bid=bid,
            ask=ask,
            submitted_at=start + timedelta(minutes=i),
            filled_at=start + timedelta(minutes=i, seconds=delay),
            venue=venue,
            commission=0.50,
            fees=0.10,
            metadata={"broker": broker, "strategy": "VERTICAL"},
        ))
    return rows


def main():
    profile = ExecutionAggregationService().analyze(build_fills())
    assert profile.valid is True
    assert profile.order_count == 5
    assert profile.venue_count == 3
    assert profile.broker_count == 3
    assert len(profile.orders) == 5
    assert len(profile.venues) == 3
    assert len(profile.brokers) == 3
    assert profile.best_venue in {"CBOE", "ISE", "BOX"}
    assert profile.worst_venue in {"CBOE", "ISE", "BOX"}
    assert profile.best_broker.startswith("BROKER_")
    assert profile.aggregate_execution_grade in {"A", "B", "C", "D", "F"}
    assert 0.0 <= profile.aggregate_execution_score <= 100.0
    assert profile.benchmarks and profile.benchmarks[0].valid
    assert [v.rank for v in profile.venues] == [1, 2, 3]
    assert all(v.order_count >= 1 for v in profile.venues)
    payload = execution_aggregation_to_dict(profile)
    json.dumps(payload)
    assert payload["orders"][0]["execution_profile"]["fills"][0]["submitted_at"].startswith("2026-")
    empty = ExecutionAggregationService().analyze([])
    assert empty.valid is False
    assert "NO_EXECUTION_FILLS" in empty.warnings
    print("All execution-aggregation assertions passed.")


if __name__ == "__main__":
    main()
