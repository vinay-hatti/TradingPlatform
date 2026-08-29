import argparse,json
from pathlib import Path
from trading_ai.market_intelligence.service import MarketIntelligenceService

def main():
 p=argparse.ArgumentParser();p.add_argument('--universe',default='canonical');p.add_argument('--no-persist',action='store_true');p.add_argument('--output',default='reports/m46/market_intelligence_latest.json');a=p.parse_args()
 snap=MarketIntelligenceService().build(a.universe,persist=not a.no_persist);path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(snap.to_dict(),indent=2));print(f'Market Intelligence: correlation={snap.correlation.get("regime")}, sentiment={snap.sentiment.get("sentiment_label")}, risk={snap.risk.get("risk_regime")}');print(path)
if __name__=='__main__':main()
