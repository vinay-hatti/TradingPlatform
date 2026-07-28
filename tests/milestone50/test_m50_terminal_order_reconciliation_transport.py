from __future__ import annotations

import threading

from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport


class _App:
    def __init__(self):
        self.order_rows = {
            7: {
                "broker_order_id": 7,
                "permanent_id": 70,
                "client_id": 50,
                "status": "Submitted",
                "filled_quantity": 0.0,
                "remaining_quantity": 1.0,
                "average_fill_price": 0.0,
                "raw": {},
            }
        }
        self.completed_order_rows = {
            8: {
                "broker_order_id": 8,
                "permanent_id": 80,
                "client_id": 50,
                "status": "Cancelled",
                "filled_quantity": 0.0,
                "remaining_quantity": 1.0,
                "average_fill_price": 0.0,
                "raw": {"source": "COMPLETED_ORDERS"},
            }
        }
        self.orders_ready = threading.Event()
        self.completed_orders_ready = threading.Event()
        self.orders_ready.set()
        self.completed_orders_ready.set()

    def isConnected(self):
        return True

    def begin_orders(self):
        self.orders_ready.set()

    def reqOpenOrders(self):
        pass

    def begin_completed_orders(self):
        self.completed_orders_ready.set()

    def reqCompletedOrders(self, api_only):
        assert api_only is False


class _Config:
    timeout_seconds = 0.1


def test_order_statuses_combines_open_and_completed_orders():
    transport = IbapiPaperOrderTransport()
    transport._app = _App()
    transport._config = _Config()
    statuses = transport.order_statuses("DU123")
    by_id = {row.broker_order_id: row for row in statuses}
    assert set(by_id) == {7, 8}
    assert by_id[8].status == "Cancelled"
