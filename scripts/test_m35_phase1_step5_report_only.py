from __future__ import annotations
import csv, hashlib, json, tempfile
from pathlib import Path
from trading_ai.scanner.universe_pipeline import UniversePipelinePolicy, UniversePipelineService

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); u=root/'data/universe'; m=root/'data/market'; u.mkdir(parents=True); m.mkdir(parents=True)
        canonical='symbol\nAAPL\n'; metrics='symbol,as_of,price,average_daily_volume,average_daily_dollar_volume,bid_ask_spread_pct,market_cap,option_volume,option_open_interest,halted\nAAPL,2026-07-20,100,500000,50000000,0.01,1000000000,100,1000,false\n'
        (u/'us_listed_equities_etfs.csv').write_text(canonical); (m/'liquidity_metrics.csv').write_text(metrics)
        (u/'eligible_universe.csv').write_text('symbol\nAAPL\n'); (u/'rejected_universe.csv').write_text('symbol\n')
        (u/'universe_manifest.json').write_text(json.dumps({'csv_sha256':hashlib.sha256(canonical.encode()).hexdigest(),'symbol_count':1}))
        (m/'liquidity_metrics_manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(metrics.encode()).hexdigest(),'metrics_count':1}))
        result=UniversePipelineService(UniversePipelinePolicy(minimum_symbol_count=1)).run(providers=[],report_only=True,universe_dir=u,market_dir=m,report_dir=root/'reports')
        assert result.status == 'READY', result.error
        assert result.eligible_count == 1
    print('M35 Phase 1 Step 5 report-only integrity assertions passed.')
if __name__=='__main__': main()
