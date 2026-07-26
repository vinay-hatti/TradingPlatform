from pathlib import Path
from trading_ai.market_intelligence.ingestion_orchestrator import PhaseRunner, UnifiedIngestionProfile


def main():
    runner=PhaseRunner(continue_on_error=True)
    ready=runner.run('ready',lambda:{'status':'READY','rows_written':3,'value':7})
    assert ready.successful and ready.rows_written==3 and ready.details['value']==7
    failed=runner.run('failed',lambda:1/0)
    assert failed.status=='FAILED' and 'ZeroDivisionError' in (failed.error or '')
    skipped=runner.run('skipped',lambda:{},skipped=True)
    assert skipped.status=='SKIPPED'
    profile=UnifiedIngestionProfile('run','start','end','FAILED',2,runner.results)
    payload=profile.to_dict()
    assert payload['phases'][0]['name']=='ready'

    script=Path(__file__).with_name('run_market_ingestion.py').read_text()
    required=(
        'timestamped_option_snapshot','volatility_snapshots','liquidity_snapshots',
        'dealer_positioning','market_overview','market_intelligence','--ingestion-report',
        'PolygonDerivedSnapshotPublisher',
    )
    for token in required: assert token in script, token
    module=Path(__file__).parents[1]/'src/trading_ai/market_intelligence/ingestion_orchestrator.py'
    text=module.read_text()
    for table in ('option_snapshot_run','option_contract_snapshot','underlying_volatility_snapshot','microstructure_liquidity_snapshot'):
        assert table in text, table
    assert 'CAPABILITY_UNAVAILABLE' in text
    assert "provider, capture_status" in text
    print('Milestone 46.2 unified market ingestion assertions passed.')

if __name__=='__main__': main()
