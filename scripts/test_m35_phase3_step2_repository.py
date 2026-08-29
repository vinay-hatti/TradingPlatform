from datetime import date
from sqlalchemy import Column,Date,Float,Integer,MetaData,String,Table,create_engine
def build():
 e=create_engine("sqlite+pysqlite:///:memory:");m=MetaData();t=Table("option_contract_history",m,Column("underlying_symbol",String),Column("expiry",Date),Column("quote_date",Date),Column("strike",Float),Column("option_type",String),Column("bid",Float),Column("ask",Float),Column("last",Float),Column("volume",Integer),Column("open_interest",Integer),Column("implied_volatility",Float),Column("delta",Float),Column("gamma",Float),Column("theta",Float),Column("vega",Float));m.create_all(e);return e,t

from trading_ai.scanner.options_market_data_quality.repository import HistoricalOptionChainRepository,OptionChainQuery
def main():
 e,t=build();row={'underlying_symbol':'AAPL','expiry':date(2026,8,21),'quote_date':date(2026,7,20),'strike':250.0,'option_type':'CALL','bid':5.0,'ask':5.3,'last':5.2,'volume':100,'open_interest':1000,'implied_volatility':.35,'delta':.45,'gamma':.02,'theta':-.08,'vega':.15}
 with e.begin() as c:c.execute(t.insert(),[row])
 r=HistoricalOptionChainRepository(e);records=r.fetch_records(OptionChainQuery(('AAPL','MSFT'),date(2026,7,20),date(2026,7,20)));assert len(records)==1 and records[0].identity.underlying_symbol=='AAPL';assert r.count_records(['AAPL'],date(2026,7,20),date(2026,7,20))==1
 print('Milestone 35 Phase 3 Step 2 repository assertions passed.')
if __name__=='__main__':main()
