from __future__ import annotations
import json
from pathlib import Path

REFERENCE_OPTIONS_SECONDS = 1313.02
REFERENCE_DEALER_SECONDS = 248.62
REFERENCE_DEALER_INSERT_SECONDS = 76.6207
REFERENCE_DEALER_COMPUTE_SECONDS = 123.4657
ORIGINAL_OPTIONS_SECONDS = 1585.00


def pct(before, after):
    return ((before-after)/before*100.0) if before else 0.0


def latest_manifest_cycle(path: Path):
    data=json.loads(path.read_text())
    cid=data.get('latest_cycle_id')
    return cid, (data.get('cycles') or {}).get(cid,{}) if cid else {}


def main():
    root=Path(__file__).resolve().parents[1]
    lifecycle=json.loads((root/'reports/market_ingestion/options_lifecycle_latest.json').read_text())
    dealer=json.loads((root/'reports/market_ingestion/dealer_positioning_latest.json').read_text())
    cid,cycle=latest_manifest_cycle(root/'reports/market_ingestion/options_manifest.json')
    meta=cycle.get('metadata') or {}; perf=meta.get('performance') or {}
    current=float(lifecycle.get('elapsed_seconds') or 0); dealer_wall=float(perf.get('dealer_seconds') or 0)
    if not current or not dealer_wall: raise RuntimeError('Run one governed options cycle after M68.2.1.15.8.5 first.')
    totals=dealer.get('timing_totals') or {}; profile=dealer.get('persistence_profile') or {}
    insert=float(totals.get('bulk_insert_seconds',0) or 0); compute=float(dealer.get('compute_seconds',0) or 0)
    print('=== M68.2.1.15.8.5 PERFORMANCE ===')
    print(f'cycle_id                         : {cid}')
    print(f'reference_options_seconds        : {REFERENCE_OPTIONS_SECONDS:.2f}')
    print(f'current_options_seconds          : {current:.2f}')
    print(f'time_saved_seconds               : {REFERENCE_OPTIONS_SECONDS-current:.2f}')
    print(f'reduction_pct                    : {pct(REFERENCE_OPTIONS_SECONDS,current):.2f}%')
    print(f'cumulative_vs_original_pct       : {pct(ORIGINAL_OPTIONS_SECONDS,current):.2f}%')
    print(f'cumulative_speedup               : {ORIGINAL_OPTIONS_SECONDS/current:.3f}x')
    print('\n--- Dealer COPY persistence ---')
    print(f'reference_dealer_seconds         : {REFERENCE_DEALER_SECONDS:.2f}')
    print(f'current_dealer_seconds           : {dealer_wall:.2f}')
    print(f'dealer_reduction_pct             : {pct(REFERENCE_DEALER_SECONDS,dealer_wall):.2f}%')
    print(f'persistence_mode                 : {profile.get("mode","UNKNOWN")}')
    print(f'copy_used                        : {profile.get("copy_used",False)}')
    print(f'reference_insert_seconds         : {REFERENCE_DEALER_INSERT_SECONDS:.4f}')
    print(f'current_insert_seconds           : {insert:.4f}')
    print(f'insert_reduction_pct             : {pct(REFERENCE_DEALER_INSERT_SECONDS,insert):.2f}%')
    print(f'dealer_preload_seconds           : {float(dealer.get("preload_seconds",0) or 0):.4f}')
    print(f'dealer_compute_wall_seconds      : {compute:.4f}')
    print(f'dealer_persistence_seconds       : {float(dealer.get("persistence_seconds",0) or 0):.4f}')
    print('\n--- Dealer compute domains (aggregate worker-seconds) ---')
    for k in sorted(totals):
        if k.startswith('compute_domain_'):
            print(f'{k:<42}: {float(totals[k] or 0):.4f}')
    print('\n--- Dealer compute domains (max single-symbol seconds) ---')
    for k,v in sorted((dealer.get('timing_max') or {}).items()):
        if k.startswith('compute_domain_'):
            print(f'{k:<42}: {float(v or 0):.4f}')
    print('\n--- Lineage integrity ---')
    print(f'governed_option_rows             : {meta.get("governed_option_rows",0)}')
    print(f'valid_records                    : {meta.get("valid_records",0)}')
    print(f'stale_daily_rows_pruned          : {meta.get("stale_daily_rows_pruned",0)}')
    print(f'completed_successfully           : {meta.get("completed_successfully",False)}')
    return 0

if __name__=='__main__': raise SystemExit(main())
