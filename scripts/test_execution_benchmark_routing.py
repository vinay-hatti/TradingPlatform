import json
from datetime import datetime, timedelta

from trading_ai.strategy_engine.execution_analytics_profile import ExecutionFill
from trading_ai.strategy_engine.execution_benchmark_serialization import execution_benchmark_to_dict
from trading_ai.strategy_engine.execution_benchmark_service import ExecutionBenchmarkService
from trading_ai.strategy_engine.execution_routing_serialization import execution_routing_to_dict
from trading_ai.strategy_engine.execution_routing_service import ExecutionRoutingService


def build_fills():
    now = datetime(2026, 7, 13, 14, 30)
    fills = []
    specs = [
        ("O1", "AAPL", "BUY", "CBOE", "BROKER_A", 100.0, 100.02, 100.04, 99.98, 100.06, 100.01, 2),
        ("O2", "MSFT", "SELL", "CBOE", "BROKER_A", 200.0, 199.98, 199.96, 199.94, 200.02, 199.99, 3),
        ("O3", "JPM", "BUY", "ISE", "BROKER_B", 50.0, 50.04, 50.10, 50.00, 50.08, 50.03, 8),
        ("O4", "NVDA", "SELL", "ISE", "BROKER_B", 150.0, 149.94, 149.85, 149.88, 150.02, 149.93, 12),
        ("O5", "AMZN", "BUY", "CBOE", "BROKER_A", 180.0, 180.02, 180.05, 179.98, 180.06, 180.01, 4),
        ("O6", "META", "SELL", "ISE", "BROKER_B", 300.0, 299.95, 299.82, 299.88, 300.02, 299.94, 15),
    ]
    for order_id, symbol, side, venue, broker, decision, arrival, fill, bid, ask, vwap, delay in specs:
        fills.append(ExecutionFill(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity_requested=10,
            quantity_filled=10,
            decision_price=decision,
            arrival_price=arrival,
            fill_price=fill,
            bid=bid,
            ask=ask,
            submitted_at=now,
            filled_at=now + timedelta(seconds=delay),
            venue=venue,
            metadata={"broker": broker, "vwap": vwap},
        ))
    return fills


def main():
    fills = build_fills()
    benchmark = ExecutionBenchmarkService().analyze(fills)
    assert benchmark.valid is True
    assert benchmark.benchmark_count == 4
    assert {item.benchmark_name for item in benchmark.summaries} == {"DECISION_PRICE", "ARRIVAL_PRICE", "MIDPOINT", "VWAP"}
    assert benchmark.order_count == 6
    assert all(item.valid for item in benchmark.summaries)

    routing, benchmark_from_routing = ExecutionRoutingService().analyze(fills)
    assert routing.valid is True
    assert routing.recommended_venue == "CBOE"
    assert routing.recommended_broker == "BROKER_A"
    assert len(routing.venue_recommendations) == 2
    assert len(routing.broker_recommendations) == 2
    assert routing.venue_recommendations[0].recommended is True
    assert routing.routing_score >= routing.venue_recommendations[-1].route_score * 0.5
    assert benchmark_from_routing.valid is True

    json.dumps(execution_benchmark_to_dict(benchmark))
    json.dumps(execution_routing_to_dict(routing))

    empty = ExecutionBenchmarkService().analyze([])
    assert empty.valid is False
    assert "NO_EXECUTION_FILLS" in empty.warnings

    print("All execution benchmark and routing assertions passed.")


if __name__ == "__main__":
    main()
