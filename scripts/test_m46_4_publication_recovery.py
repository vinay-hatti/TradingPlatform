from pathlib import Path

root=Path(__file__).resolve().parents[1]
script=(root/'scripts/run_market_ingestion.py').read_text()
pub=(root/'src/trading_ai/market_intelligence/publication.py').read_text()
migration=(root/'migrations/versions/m46_003_ingestion_publication.py').read_text()
recovery=(root/'scripts/run_m46_ingestion_recovery.py').read_text()
assert 'scanner_readiness' in script
assert 'publish_current_snapshot' in script
assert '--skip-publication' in script
assert 'market_ingestion_publication' in migration
assert 'revision = "m46_003"' in migration
assert 'down_revision = "m46_002"' in migration
assert 'class ScannerReadinessService' in pub
assert 'ON CONFLICT (publication_name) DO UPDATE' in pub
assert 'Full ingestion is required for failed data-capture phases' in recovery
print('Milestone 46.4 publication and recovery assertions passed.')
