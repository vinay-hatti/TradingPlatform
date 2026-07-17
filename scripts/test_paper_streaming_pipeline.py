from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trading_ai.market.paper_streaming_adapter import PaperStreamingAdapter
from trading_ai.market.realtime_event_dispatcher import (
    RealTimeMarketEventDispatcher,
)
from trading_ai.market.realtime_market_data_pipeline import (
    NormalizedMarketDataPipeline,
)
from trading_ai.market.realtime_pipeline_serialization import dumps
from trading_ai.market.realtime_provider_profile import SubscriptionRequest
from trading_ai.market.realtime_provider_service import RealTimeProviderService


def main() -> None:
    now = datetime.now(timezone.utc)
    adapter = PaperStreamingAdapter()
    provider_service = RealTimeProviderService(adapter)
    dispatcher = RealTimeMarketEventDispatcher()
    pipeline = NormalizedMarketDataPipeline(dispatcher=dispatcher)
    pipeline.bind_adapter(adapter)

    delivered = []
    quotes_only = []

    dispatcher.subscribe(
        "all-events",
        delivered.append,
        event_types=("QUOTE", "TRADE"),
    )
    dispatcher.subscribe(
        "aapl-quotes",
        quotes_only.append,
        event_types=("QUOTE",),
        symbols=("AAPL",),
    )

    connection = provider_service.connect()
    assert connection.allowed
    subscription = provider_service.subscribe(
        SubscriptionRequest(
            subscription_id="paper-core",
            provider="paper",
            symbols=("AAPL", "MSFT"),
            channels=("QUOTES", "TRADES"),
        ),
        persist=False,
    )
    assert subscription.status == "ACTIVE"

    adapter.queue_quote(
        "AAPL",
        bid_price=199.9,
        ask_price=200.1,
        bid_size=10,
        ask_size=12,
        exchange_timestamp=now - timedelta(milliseconds=100),
        received_timestamp=now,
    )
    adapter.queue_trade(
        "AAPL",
        price=200.0,
        size=100,
        exchange_timestamp=now - timedelta(milliseconds=90),
        received_timestamp=now,
    )
    adapter.queue_quote(
        "MSFT",
        bid_price=499.0,
        ask_price=501.0,
        bid_size=20,
        ask_size=20,
        exchange_timestamp=now - timedelta(milliseconds=80),
        received_timestamp=now,
    )
    adapter.queue_quote(
        "AAPL",
        bid_price=210.0,
        ask_price=209.0,
        bid_size=5,
        ask_size=5,
        exchange_timestamp=now - timedelta(milliseconds=70),
        received_timestamp=now,
    )

    emitted = adapter.emit_all()
    assert len(emitted) == 4
    assert pipeline.pending_count() == 4

    results = pipeline.process_all()
    assert len(results) == 4
    assert sum(item.accepted for item in results) == 3
    assert len(delivered) == 3
    assert len(quotes_only) == 1
    assert quotes_only[0].symbol == "AAPL"

    rejected = pipeline.rejected_events()
    assert len(rejected) == 1
    assert "CROSSED_QUOTE" in rejected[0].rejection_reasons

    health = pipeline.health()
    assert health.received_count == 4
    assert health.accepted_count == 3
    assert health.rejected_count == 1
    assert health.quote_count == 3
    assert health.trade_count == 1
    assert health.subscriber_count == 2
    assert health.state == "RUNNING"

    serialized = dumps(health)
    assert '"received_count": 4' in serialized
    assert '"accepted_count": 3' in serialized

    provider_service.disconnect()
    assert not adapter.is_connected()

    print(
        "All paper-streaming, event-dispatcher and normalized-pipeline "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
