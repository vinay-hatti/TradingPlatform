from datetime import datetime, timezone
from trading_ai.polygon_intelligence import HistoricalVolatilityEngine, MicrostructureLiquidityEngine, InstitutionalMarketContext, InstitutionalMarketIntelligencePolicy

def main():
    h=[.20+i*.001 for i in range(30)]
    assert HistoricalVolatilityEngine.iv_rank(.225,h)['status']=='READY'
    assert HistoricalVolatilityEngine.iv_percentile(.225,h)['value']>0
    assert HistoricalVolatilityEngine.iv_rank(.2,[.2]*5)['status']=='INSUFFICIENT_HISTORY'
    m=MicrostructureLiquidityEngine.snapshot_metrics([{'bid':1,'ask':1.1},{'bid':2,'ask':2.1}],[{'size':10},{'size':20}])
    assert m['average_trade_size']==15
    assert m['depth_available'] is False
    p=InstitutionalMarketIntelligencePolicy()
    neutral=p.evaluate(None,direction='CALL',strategy_family='LONG_PREMIUM')
    assert neutral.allowed and neutral.total_adjustment==0
    c=InstitutionalMarketContext(snapshot_timestamp=datetime.now(timezone.utc),market_sentiment_score=70,market_risk_score=30,sector_breadth_score=70,dealer_positioning_score=65,liquidity_regime='NORMAL',strategy_fit='LONG_PREMIUM_FAVORABLE',confidence=80,freshness_status='CURRENT',provenance='MODEL_DERIVED')
    r=p.evaluate(c,direction='CALL',strategy_family='LONG_PREMIUM')
    assert r.total_adjustment>0 and r.outcome in {'SUPPORTIVE','CONDITIONALLY_SUPPORTIVE'}
    b=p.evaluate(c,direction='PUT',strategy_family='LONG_PREMIUM')
    assert b.total_adjustment<r.total_adjustment
    print('Milestone 46 Polygon closure assertions passed.')
if __name__=='__main__':main()
