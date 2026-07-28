from trading_ai.broker.ibkr.order_service import IbkrPaperOrderService


def test_terminal_broker_status_mapping():
    assert IbkrPaperOrderService._canonical_state("Filled") == "FILLED"
    assert IbkrPaperOrderService._canonical_state("Cancelled") == "CANCELED"
    assert IbkrPaperOrderService._canonical_state("ApiCancelled") == "CANCELED"
    assert IbkrPaperOrderService._canonical_state("Inactive") == "REJECTED"
    assert IbkrPaperOrderService._canonical_state("Submitted") == "SUBMITTED"
