from pathlib import Path
root=Path(__file__).resolve().parents[1]
checks={
 'migration':('migrations/versions/m46_001_market_intelligence.py',['sector_membership','correlation_pair_snapshot','market_sentiment_snapshot','dealer_position_change_snapshot','market_opportunity_snapshot']),
 'api':('src/trading_ai/market_intelligence/router.py',['/correlation','/sectors','/dealer-migration','/risk','/opportunities']),
 'scanner':('src/trading_ai/daily/scanner.py',['sector_score_adjustment','risk_score_adjustment','intelligence_adjustments']),
 'ui':('ui/workstation/src/pages.tsx',['Correlation regime','Sentiment ensemble','Constituent sector breadth','Dealer positioning trend & migration','Institutional opportunity dashboard']),
 'ingestion':('scripts/run_market_ingestion.py',['skip-market-intelligence','MarketIntelligenceService']),
}
for name,(path,tokens) in checks.items():
 text=(root/path).read_text()
 for token in tokens: assert token in text,(name,token)
print('Milestone 46 integration contract assertions passed.')
