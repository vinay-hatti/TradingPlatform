from datetime import datetime,timedelta,timezone
from trading_ai.market.realtime_market_data_policy import RealTimeMarketDataPolicy
from trading_ai.market.realtime_market_data_profile import RawQuoteEvent,RawTradeEvent,MarketDataSourceProfile
from trading_ai.market.realtime_market_data_service import RealTimeMarketDataService
from trading_ai.market.realtime_market_data_serialization import dumps

def main():
    now=datetime.now(timezone.utc)
    service=RealTimeMarketDataService(RealTimeMarketDataPolicy(maximum_quote_age_seconds=5,maximum_trade_age_seconds=10,maximum_spread_pct=.05,warning_spread_pct=.02,minimum_quote_size=1,minimum_trade_size=1))
    q=service.process_quote(RawQuoteEvent('aapl','199.90','200.10','10','12',now-timedelta(milliseconds=150),now-timedelta(milliseconds=50),now,source=MarketDataSourceProfile(provider='test')))
    assert q.allowed and q.quote.symbol=='AAPL' and q.quote.midpoint==200 and round(q.quote.spread,2)==.20
    dq=service.process_quote({'symbol':'msft','bid_price':499,'ask_price':501,'bid_size':20,'ask_size':20,'exchange_timestamp':int((now-timedelta(milliseconds=100)).timestamp()*1000),'received_timestamp':now.isoformat(),'source':{'provider':'mapping'}})
    assert dq.allowed and dq.quote.source.provider=='mapping'
    wide=service.process_quote({'symbol':'SPY','bid_price':400,'ask_price':430,'bid_size':5,'ask_size':5,'exchange_timestamp':now,'received_timestamp':now}); assert not wide.allowed and 'SPREAD' in wide.rejection_reasons
    crossed=service.process_quote({'symbol':'QQQ','bid_price':510,'ask_price':509,'bid_size':5,'ask_size':5,'exchange_timestamp':now,'received_timestamp':now}); assert not crossed.allowed and 'CROSSED_QUOTE' in crossed.rejection_reasons
    stale=service.process_quote({'symbol':'IWM','bid_price':200,'ask_price':200.2,'bid_size':5,'ask_size':5,'exchange_timestamp':now-timedelta(seconds=30),'received_timestamp':now}); assert not stale.allowed and stale.quality.stale and 'STALE_QUOTE' in stale.rejection_reasons
    out=service.process_quote({'symbol':'DIA','bid_price':450,'ask_price':450.2,'bid_size':5,'ask_size':5,'exchange_timestamp':now-timedelta(seconds=3),'received_timestamp':now},previous_exchange_timestamp=now); assert not out.allowed and out.quality.out_of_order and 'OUT_OF_ORDER' in out.rejection_reasons
    t=service.process_trade(RawTradeEvent('aapl','200.05','100',now-timedelta(milliseconds=200),received_timestamp=now,exchange='XNAS',source={'provider':'test'})); assert t.allowed and t.trade.notional==20005
    st=service.process_trade({'symbol':'AAPL','price':200,'size':10,'exchange_timestamp':now-timedelta(seconds=30),'received_timestamp':now}); assert st.allowed and st.quality.stale and 'STALE_TRADE' in st.warnings
    s=dumps(q); assert '"symbol": "AAPL"' in s and '"recommendation": "ACCEPT"' in s
    print('All real-time market-data contracts, normalization and quality-foundation assertions passed.')
if __name__=='__main__': main()
