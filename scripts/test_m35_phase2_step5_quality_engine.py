from datetime import date
from trading_ai.scanner.market_data_quality.quality import *
def main():
    e=MarketDataQualityEngine(MarketDataQualityPolicy(lookback_rows=5))
    b=lambda d,o,h,l,c,v:PriceBar("AAPL",d,o,h,l,c,v)
    clean=e.evaluate_symbol("AAPL",[b(date(2026,7,17),100,102,99,101,1000),b(date(2026,7,20),101,103,100,102,1200)])
    assert clean.status is QualityStatus.READY and clean.quality_score==100
    bad=e.evaluate_symbol("AAPL",[b(date(2026,7,17),100,90,95,101,-1),b(date(2026,7,20),101,103,100,200,0)])
    assert bad.invalid_ohlc_rows and bad.negative_volume_rows and bad.extreme_return_rows
    print("Milestone 35 Phase 2 Step 5 quality engine assertions passed.")
if __name__=="__main__":main()
