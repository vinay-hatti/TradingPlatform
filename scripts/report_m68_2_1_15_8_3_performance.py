from __future__ import annotations
import json
from pathlib import Path

PHASE3_OPTIONS_SECONDS = 1294.56
PHASE3_CAPTURE_SECONDS = 528.53
PHASE3_DEALER_SECONDS = 262.59
PHASE3_VALUATION_SECONDS = 40.9309
ORIGINAL_OPTIONS_SECONDS = 1585.00


def pct(before, after):
    return ((before-after)/before*100.0) if before else 0.0


def latest_manifest_cycle(path: Path):
    data = json.loads(path.read_text())
    cycle_id = data.get("latest_cycle_id")
    cycle = (data.get("cycles") or {}).get(cycle_id, {}) if cycle_id else {}
    return cycle_id, cycle


def main():
    root = Path(__file__).resolve().parents[1]
    lifecycle = json.loads((root / "reports/market_ingestion/options_lifecycle_latest.json").read_text())
    dealer = json.loads((root / "reports/market_ingestion/dealer_positioning_latest.json").read_text())
    cycle_id, cycle = latest_manifest_cycle(root / "reports/market_ingestion/options_manifest.json")
    metadata = cycle.get("metadata") or {}
    performance = metadata.get("performance") or {}
    polygon = performance.get("polygon_capture") or {}
    current = float(lifecycle.get("elapsed_seconds") or 0)
    capture = float(performance.get("capture_seconds") or 0)
    dealer_wall = float(performance.get("dealer_seconds") or 0)
    if not current or not capture:
        raise RuntimeError("Run one governed options cycle after M68.2.1.15.8.3 first.")

    print("=== M68.2.1.15.8.3 PERFORMANCE ===")
    print(f"cycle_id                     : {cycle_id}")
    print(f"phase3_options_seconds       : {PHASE3_OPTIONS_SECONDS:.2f}")
    print(f"current_options_seconds      : {current:.2f}")
    print(f"phase3_time_saved_seconds    : {PHASE3_OPTIONS_SECONDS-current:.2f}")
    print(f"phase3_reduction_pct         : {pct(PHASE3_OPTIONS_SECONDS,current):.2f}%")
    print(f"cumulative_vs_original_pct   : {pct(ORIGINAL_OPTIONS_SECONDS,current):.2f}%")
    print(f"cumulative_speedup           : {ORIGINAL_OPTIONS_SECONDS/current:.3f}x")
    print()
    print("--- Polygon capture ---")
    print(f"phase3_capture_seconds       : {PHASE3_CAPTURE_SECONDS:.2f}")
    print(f"current_capture_seconds      : {capture:.2f}")
    print(f"capture_reduction_pct        : {pct(PHASE3_CAPTURE_SECONDS,capture):.2f}%")
    print(f"capture_execution_mode       : {polygon.get('execution_mode','UNKNOWN')}")
    print(f"network_workers              : {polygon.get('network_workers',0)}")
    print(f"global_rps_limit             : {polygon.get('requests_per_second_limit',0)}")
    print(f"request_count                : {polygon.get('request_count',0)}")
    print(f"aggregate_http_seconds       : {polygon.get('aggregate_http_seconds',0)}")
    print(f"aggregate_throttle_wait      : {polygon.get('aggregate_throttle_wait_seconds',0)}")
    print()
    print("--- Dealer profiling ---")
    print(f"phase3_dealer_seconds        : {PHASE3_DEALER_SECONDS:.2f}")
    print(f"current_dealer_seconds       : {dealer_wall:.2f}")
    print(f"dealer_reduction_pct         : {pct(PHASE3_DEALER_SECONDS,dealer_wall):.2f}%")
    print(f"dealer_execution_mode        : {dealer.get('execution_mode','UNKNOWN')}")
    print(f"dealer_workers               : {dealer.get('worker_count',0)}")
    print(f"dealer_preload_seconds       : {dealer.get('preload_seconds',0)}")
    totals = dealer.get("timing_totals") or {}
    for key in ("input_seconds","compute_seconds","persistence_seconds","persistence_merge_seconds","persistence_delete_seconds","persistence_prepare_seconds","persistence_commit_seconds","report_seconds"):
        print(f"dealer_sum_{key:<25}: {float(totals.get(key,0) or 0):.4f}")
    print()
    print(f"Reference valuation          : {PHASE3_VALUATION_SECONDS:.4f}s")
    print(f"governed_option_rows         : {metadata.get('governed_option_rows',0)}")
    print(f"valid_records                : {metadata.get('valid_records',0)}")
    print(f"stale_daily_rows_pruned      : {metadata.get('stale_daily_rows_pruned',0)}")
    print(f"completed_successfully       : {metadata.get('completed_successfully',False)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
