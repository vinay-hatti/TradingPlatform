from trading_ai.broker.ibkr.order_models import IbkrPaperOrderRequest

def test_request_validation():
    IbkrPaperOrderRequest(aggregate_id='A',client_order_id='C',portfolio_id='PAPER-PRIMARY',broker_account_id='DU123',symbol='AAPL',security_type='STK',side='BUY',quantity=1).validate()

def test_live_account_rejected():
    try:
        IbkrPaperOrderRequest(aggregate_id='A',client_order_id='C',portfolio_id='P',broker_account_id='U123',symbol='AAPL',security_type='STK',side='BUY',quantity=1).validate()
    except ValueError as exc: assert 'DU' in str(exc)
    else: raise AssertionError('live/non-paper account accepted')

def test_limit_requires_price():
    try:
        IbkrPaperOrderRequest(aggregate_id='A',client_order_id='C',portfolio_id='P',broker_account_id='DU123',symbol='AAPL',security_type='STK',side='BUY',quantity=1,order_type='LMT').validate()
    except ValueError as exc: assert 'limit_price' in str(exc)
    else: raise AssertionError('limit order without price accepted')
