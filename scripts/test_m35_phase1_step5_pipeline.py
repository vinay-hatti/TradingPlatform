from __future__ import annotations

import csv
import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from trading_ai.scanner.universe_management import FileUniverseProvider, LiquidityGovernancePolicy
from trading_ai.scanner.universe_management.liquidity_metrics_builder import LiquidityMetricsBuildPolicy
from trading_ai.scanner.universe_pipeline import UniversePipelinePolicy, UniversePipelineService


def write_universe(path: Path, count: int = 20) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['symbol','name','exchange','asset_type','is_etf','options_eligible','active','primary_source'])
        writer.writeheader()
        for i in range(count):
            writer.writerow({'symbol':f'T{i:04d}','name':f'Test {i}','exchange':'NASDAQ','asset_type':'EQUITY','is_etf':'false','options_eligible':'true','active':'true','primary_source':'TEST'})


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); source=root/'source.csv'; write_universe(source)
        engine=create_engine('sqlite://')
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE price_history (symbol TEXT, date DATE, close FLOAT, volume FLOAT)'))
            conn.execute(text('CREATE TABLE option_contract_history (underlying_symbol TEXT, quote_date DATE, bid FLOAT, ask FLOAT, volume FLOAT, open_interest FLOAT)'))
            today=date.today()
            for i in range(20):
                for d in range(10):
                    conn.execute(text('INSERT INTO price_history VALUES (:s,:d,:c,:v)'), {'s':f'T{i:04d}','d':today-timedelta(days=d),'c':100+i,'v':500000})
                conn.execute(text('INSERT INTO option_contract_history VALUES (:s,:d,1.0,1.05,100,1000)'), {'s':f'T{i:04d}','d':today})
        ref=root/'reference.csv'
        with ref.open('w',newline='',encoding='utf-8') as handle:
            w=csv.DictWriter(handle,fieldnames=['symbol','market_cap','halted']); w.writeheader()
            for i in range(20): w.writerow({'symbol':f'T{i:04d}','market_cap':1000000000,'halted':'false'})
        with Session(engine) as session:
            result=UniversePipelineService(UniversePipelinePolicy(minimum_symbol_count=20)).run(
                providers=[FileUniverseProvider(source,name='TEST')], session=session,
                universe_dir=root/'data/universe', market_dir=root/'data/market', report_dir=root/'reports/pipeline',
                universe_refresh_report_dir=root/'reports/universe', liquidity_metrics_report_dir=root/'reports/metrics', liquidity_report_dir=root/'reports/liquidity',
                reference_csv=ref, liquidity_policy=LiquidityGovernancePolicy(minimum_market_cap=1, minimum_average_daily_volume=1, minimum_average_daily_dollar_volume=1, maximum_bid_ask_spread_pct=1),
                metrics_policy=LiquidityMetricsBuildPolicy(minimum_price_observations=5),
            )
        assert result.status == 'READY', result.error
        assert result.universe_count == 20 and result.metrics_count == 20 and result.eligible_count == 20
        for name in ('pipeline_summary.json','pipeline_summary.html','pipeline_manifest.json','provider_health.json','cache_health.json'):
            assert (root/'reports/pipeline'/name).is_file(), name
        payload=json.loads((root/'reports/pipeline/pipeline_summary.json').read_text())
        assert payload['last_completed_stage'] == 'COMPLETE'
        assert all(item['exists'] for item in payload['artifacts'])
    print('M35 Phase 1 Step 5 pipeline closure assertions passed.')

if __name__ == '__main__': main()
