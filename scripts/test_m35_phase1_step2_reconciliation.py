from datetime import datetime, timezone
from trading_ai.scanner.universe_management import SecurityProfile, UniverseProviderResult, UniverseReconciliationEngine

def main():
 now=datetime.now(timezone.utc)
 a=UniverseProviderResult('NASDAQ_SYMBOL_DIRECTORY',now,(SecurityProfile('AAPL',name='Apple',exchange='NASDAQ',source='NASDAQ_SYMBOL_DIRECTORY'),SecurityProfile('SPY',exchange='NYSE_ARCA',asset_type='ETF',source='NASDAQ_SYMBOL_DIRECTORY')))
 b=UniverseProviderResult('POLYGON',now,(SecurityProfile('AAPL',name='Apple Inc',exchange='NASDAQ',options_eligible=True,source='POLYGON'),))
 r=UniverseReconciliationEngine().reconcile((a,b)); assert len(r.securities)==2; assert r.securities[0].symbol=='AAPL'; assert r.securities[0].options_eligible; assert r.metadata['conflict_count']>=1
 print('Milestone 35 Phase 1 Step 2 reconciliation assertions passed.')
if __name__=='__main__': main()
