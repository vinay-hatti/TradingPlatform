#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from trading_ai.downside_risk_veto.service import DownsideRiskVetoService,CHAMPION_ID

def main():
    p=argparse.ArgumentParser();p.add_argument('--project-root',default='/Users/vinay.hatti/TradingPlatform');a=p.parse_args();root=Path(a.project_root).resolve()
    meta=root/'data/downside_risk_veto/champion/DRVE-CHAMPION-001.json';auth=root/'data/downside_risk_veto/current_authority.json'
    if not meta.exists():raise SystemExit('FAIL: champion metadata missing')
    if not auth.exists():raise SystemExit('FAIL: current authority missing')
    m=json.loads(meta.read_text());x=json.loads(auth.read_text())
    checks={
      'champion_id':m.get('champion_id')==CHAMPION_ID,
      'final_holdout_certified':m.get('final_holdout_certified') is True,
      'feature_parity_valid':x.get('feature_parity_valid') is True,
      'model_fingerprint_match':x.get('model_fingerprint')==m.get('model_fingerprint'),
      'scored_symbols_positive':int(x.get('scored_symbol_count') or 0)>0,
      'veto_count_positive':int(x.get('veto_count') or 0)>0,
      'scope_exact':x.get('production_scope')=='TRADE_BUILDER_READY_LONG_ONLY',
    }
    print(json.dumps({'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'champion_id':m.get('champion_id'),'stock_scanner_run_id':x.get('stock_scanner_run_id'),'market_as_of_date':x.get('market_as_of_date'),'veto_count':x.get('veto_count'),'scored_symbol_count':x.get('scored_symbol_count')},indent=2,sort_keys=True))
    return 0 if all(checks.values()) else 2
if __name__=='__main__':raise SystemExit(main())
