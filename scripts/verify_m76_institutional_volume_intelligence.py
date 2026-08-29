from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1])
checks={
 'volume_engine': ('src/trading_ai/stock_intelligence/volume_intelligence.py','M76-INSTITUTIONAL-VOLUME-1.0'),
 'profile_contract': ('src/trading_ai/stock_intelligence/profile.py','institutional_volume:Any|None=None'),
 'service_integration': ('src/trading_ai/stock_intelligence/service.py','InstitutionalVolumeIntelligenceEngine'),
 'ranking_integration': ('src/trading_ai/stock_intelligence/scoring.py',"weights['volume']"),
 'publication_projection': ('src/trading_ai/stock_intelligence/publication.py','institutional_volume_signal'),
 'institutional_options_hook': ('src/trading_ai/institutional_options/opportunity_ingestion.py','Institutional volume:'),
 'scanner_ui': ('ui/workstation/src/StockIntelligenceScannerPage.tsx','Institutional volume'),
 'scanner_filter': ('ui/workstation/src/StockIntelligenceScannerPage.tsx',"headerSelect('volume', options.volume)"),
}
failed=[]
for name,(rel,needle) in checks.items():
    path=root/rel
    ok=path.exists() and needle in path.read_text()
    print(('PASS' if ok else 'FAIL'),name)
    if not ok: failed.append(name)
if failed:
    raise SystemExit('M76 verifier failed: '+', '.join(failed))
print('M76 institutional volume intelligence verification: PASSED')
