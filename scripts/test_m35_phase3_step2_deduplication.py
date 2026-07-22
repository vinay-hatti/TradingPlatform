from datetime import date
from trading_ai.scanner.options_market_data_quality import OptionContractIdentity,OptionQuoteRecord,OptionSide
from trading_ai.scanner.options_market_data_quality.deduplication import OptionContractDeduplicator
def main():
    i=OptionContractIdentity('AAPL',date(2026,8,21),250.0,OptionSide.CALL);a=OptionQuoteRecord(i,date(2026,7,20),bid=5.0);b=OptionQuoteRecord(i,date(2026,7,20),bid=5.0,ask=5.3,last=5.2,volume=100,open_interest=1000,implied_volatility=.35,delta=.45)
    r=OptionContractDeduplicator().deduplicate([a,b]);assert r.input_record_count==2 and r.unique_record_count==1 and r.duplicate_record_count==1 and r.records[0]==b
    print('Milestone 35 Phase 3 Step 2 deduplication assertions passed.')
if __name__=='__main__':main()
