from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    models=(ROOT/'src/trading_ai/daily_scan_workstation/models.py').read_text()
    service=(ROOT/'src/trading_ai/daily_scan_workstation/service.py').read_text()
    workflow=(ROOT/'scripts/run_m43_market_ingestion_workflow.py').read_text()
    page=(ROOT/'ui/workstation/src/pages.tsx').read_text()
    types=(ROOT/'ui/workstation/src/types.ts').read_text()
    assert 'data_scope: Literal["underlying", "options", "all"]' in models
    assert 'run_m43_market_ingestion_workflow.py' in service
    assert 'scripts/run_m43_refresh_market_data.py' in workflow
    assert '"--data-scope", "options"' in workflow
    assert 'Run market ingestion' in page
    assert 'Run database-only daily scan' in page
    assert 'Direct provider calls during scan' in page
    assert "data_scope:'underlying'|'options'|'all'" in types
    print('Milestone 43 ingestion/scanner UI contract assertions passed.')

if __name__ == '__main__': main()
