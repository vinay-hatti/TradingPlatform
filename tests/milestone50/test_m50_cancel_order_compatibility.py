from __future__ import annotations

from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport


class _LegacyClient:
    def __init__(self):
        self.calls = []

    def isConnected(self):
        return True

    def cancelOrder(self, order_id):
        self.calls.append((order_id,))


class _NewerClient:
    def __init__(self):
        self.calls = []

    def isConnected(self):
        return True

    def cancelOrder(self, *args):
        if len(args) == 1:
            raise TypeError("manualCancelOrderTime required")
        self.calls.append(args)


def _transport(app):
    value = IbapiPaperOrderTransport()
    value._app = app
    return value


def test_cancel_order_supports_legacy_one_argument_signature():
    app = _LegacyClient()
    _transport(app).cancel_order(17)
    assert app.calls == [(17,)]


def test_cancel_order_retries_newer_two_argument_signature():
    app = _NewerClient()
    _transport(app).cancel_order(23)
    assert app.calls == [(23, "")]
