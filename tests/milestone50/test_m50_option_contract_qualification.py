import pytest

from trading_ai.broker.ibkr.order_models import IbkrPaperOrderRequest


def _option_request(**overrides):
    values = dict(
        aggregate_id="M59-XI-TEST",
        client_order_id="M59-CLIENT-XI-TEST",
        portfolio_id="PAPER-PRIMARY",
        broker_account_id="DU123456",
        symbol="VOO",
        security_type="OPT",
        side="BUY",
        quantity=1,
        order_type="LMT",
        limit_price=5.0,
        contract_id=123456789,
        local_symbol="VOO   260918C00100000",
        expiry="20260918",
        strike=100.0,
        right="C",
        multiplier="100",
    )
    values.update(overrides)
    return IbkrPaperOrderRequest(**values)


def test_qualified_option_request_is_accepted():
    _option_request().validate()


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"contract_id": 0}, "contract_id"),
        ({"local_symbol": ""}, "local_symbol"),
        ({"expiry": ""}, "expiry"),
        ({"strike": 0}, "strike"),
        ({"right": "CALL"}, "right"),
        ({"multiplier": ""}, "multiplier"),
    ],
)
def test_unqualified_option_request_is_rejected(overrides, message):
    with pytest.raises(ValueError, match=message):
        _option_request(**overrides).validate()


def test_stock_request_remains_backward_compatible():
    IbkrPaperOrderRequest(
        aggregate_id="A",
        client_order_id="C",
        portfolio_id="PAPER-PRIMARY",
        broker_account_id="DU123456",
        symbol="AAPL",
        security_type="STK",
        side="BUY",
        quantity=1,
    ).validate()
