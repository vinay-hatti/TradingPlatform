from trading_ai.autonomous_position_management.quotes import M73LiveQuoteService
from trading_ai.execution_intelligence.provider import DirectQuote,ExecutionQuoteError


class Provider:
    def option_quote(self,underlying,option_symbol):
        return DirectQuote(option_symbol,'OPTION',100.0,101.0,100.5,1,1,100.5,'2026-08-08T20:00:00+00:00','2026-08-08T20:00:01+00:00',underlying_price=None)
    def underlying_quote(self,symbol):
        raise ExecutionQuoteError('Polygon HTTP 404: stock snapshot not found')
    def index_quote(self,symbol):
        assert symbol=='SPX'
        return DirectQuote('I:SPX','INDEX',0,0,7757.64,0,0,7757.64,'2026-08-08T20:00:00+00:00','2026-08-08T20:00:01+00:00')


def test_spx_falls_back_to_index_snapshot_when_option_has_no_underlying_price():
    svc=M73LiveQuoteService(Provider())
    out=svc.snapshot('SPX',[{'option_symbol':'O:SPX260918C07725000','side':'BUY','quantity':1}],10**9)
    assert out['underlying']['instrument']=='I:SPX'
    assert out['underlying']['instrument_type']=='INDEX'
    assert out['underlying_price']==7757.64
    assert out['underlying_fallback_used'] is True
    assert '404' in out['underlying_quote_error']
