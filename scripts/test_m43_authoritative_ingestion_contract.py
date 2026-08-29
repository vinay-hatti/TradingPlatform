from pathlib import Path

def main():
    ingestion=Path('scripts/run_market_ingestion.py').read_text()
    scanner=Path('src/trading_ai/daily/scanner.py').read_text()
    workflow=Path('scripts/run_m43_daily_scan_workflow.py').read_text()
    assert 'choices=["underlying","options","all"]' in ingestion
    assert 'PolygonOptionChainSnapshotProvider' in ingestion
    assert 'MarketDownloader' in ingestion
    assert 'RepositoryOptionSnapshotProvider' in scanner
    assert 'PolygonOptionSnapshotProvider()' not in scanner
    assert 'if not args.auto_refresh' in workflow
    print('Authoritative ingestion and cache-only scanner assertions passed.')
if __name__=='__main__': main()
