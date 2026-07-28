from __future__ import annotations

from pathlib import Path


def test_transport_exposes_monotonic_order_id_floor():
    text = Path("src/trading_ai/broker/ibkr/order_transport.py").read_text()
    assert "def set_order_id_floor" in text
    assert "app.next_id < minimum" in text


def test_service_advances_above_persisted_order_ids_and_cancels_collisions():
    text = Path("src/trading_ai/broker/ibkr/order_service.py").read_text()
    assert "func.max(BrokerOrderModel.broker_order_id)" in text
    assert "set_order_id_floor" in text
    assert "cancellation requested" in text
    assert "self.transport.cancel_order(broker_order_id)" in text
