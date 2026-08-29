from datetime import date
from sqlalchemy import *
from trading_ai.scanner.market_data_quality.quality import *
def main():
    e=create_engine("sqlite+pysqlite:///:memory:"); m=MetaData()
    t=Table("price_history",m,Column("symbol",String),Column("date",Date),Column("open",Float),Column("high",Float),Column("low",Float),Column("close",Float),Column("volume",Float));m.create_all(e)
    with e.begin() as c:c.execute(t.insert(),[{"symbol":"AAPL","date":date(2026,7,17),"open":100,"high":102,"low":99,"close":101,"volume":1000},{"symbol":"AAPL","date":date(2026,7,20),"open":101,"high":103,"low":100,"close":102,"volume":1200}])
    p=MarketDataQualityService(e,MarketDataQualityPolicy(lookback_rows=5)).evaluate(["AAPL","MSFT"],date(2026,7,20))
    assert next(x for x in p.symbol_profiles if x.symbol=="AAPL").quality_score==100
    assert next(x for x in p.symbol_profiles if x.symbol=="MSFT").quality_score==0
    print("Milestone 35 Phase 2 Step 5 quality service assertions passed.")
if __name__=="__main__":main()
