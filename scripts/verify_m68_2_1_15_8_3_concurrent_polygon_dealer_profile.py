from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
provider=(ROOT/'src/trading_ai/scanner/options_market_data_ingestion/polygon_snapshot_provider.py').read_text()
refresh=(ROOT/'src/trading_ai/institutional_market_structure/refresh.py').read_text()
service=(ROOT/'src/trading_ai/institutional_market_structure/service.py').read_text()
split=(ROOT/'scripts/ingest_options_data.py').read_text()
parser=(ROOT/'scripts/run_market_ingestion.py').read_text()
checks={
 'shared global Polygon rate limiter':'self._throttle_lock = threading.Lock()' in provider and 'with self._throttle_lock' in provider,
 'bounded concurrent symbol capture':'ThreadPoolExecutor' in provider and 'network_workers' in provider and '_capture_symbol_batches_tuple' in provider,
 'deterministic provider output':'for symbol in ordered:' in provider and 'yield batch' in provider,
 'split entrypoint enables provider workers':'network_workers=max(1, int(getattr(args, "polygon_network_workers", 4)))' in split,
 'dealer preload regression removed':'PARALLEL_SYMBOL_ISOLATED_PROFILED' in refresh and 'preloaded_by_symbol' not in refresh,
 'dealer persistence profiling':'persistence_commit_seconds' in service and 'timing_totals' in refresh,
 'CLI worker control':'--polygon-network-workers' in parser,
 'capture metrics persisted':'"polygon_capture": polygon_profile' in split,
 'scheduled jobs pin four capture workers':all('--polygon-network-workers 4' in (ROOT/'scripts/m69_6_scheduled'/name).read_text() for name in ('run_intraday.sh','run_morning.sh','run_eod.sh')),
}
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit('FAILED: '+', '.join(failed))
print('M68.2.1.15.8.3 source verification PASSED')
for k in checks: print(' - '+k)
