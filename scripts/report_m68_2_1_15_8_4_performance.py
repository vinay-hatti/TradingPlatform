from __future__ import annotations
import json
from pathlib import Path

BEST_OPTIONS_SECONDS = 1294.56  # M68.2.1.15.8.2 production best
REGRESSED_OPTIONS_SECONDS = 1475.41  # M68.2.1.15.8.3 experimental run
SERIAL_CAPTURE_REFERENCE = 528.53
PROFILED_DEALER_REFERENCE = 252.67
ORIGINAL_OPTIONS_SECONDS = 1585.00


def pct(before, after):
    return ((before - after) / before * 100.0) if before else 0.0


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
        raise RuntimeError("Run one governed options cycle after M68.2.1.15.8.4 first.")

    print("=== M68.2.1.15.8.4 PERFORMANCE ===")
    print(f"cycle_id                         : {cycle_id}")
    print(f"best_pre_1584_options_seconds    : {BEST_OPTIONS_SECONDS:.2f}")
    print(f"current_options_seconds          : {current:.2f}")
    print(f"vs_best_time_saved_seconds       : {BEST_OPTIONS_SECONDS-current:.2f}")
    print(f"vs_best_reduction_pct            : {pct(BEST_OPTIONS_SECONDS,current):.2f}%")
    print(f"vs_1583_regression_recovered     : {REGRESSED_OPTIONS_SECONDS-current:.2f}s")
    print(f"cumulative_vs_original_pct       : {pct(ORIGINAL_OPTIONS_SECONDS,current):.2f}%")
    print(f"cumulative_speedup               : {ORIGINAL_OPTIONS_SECONDS/current:.3f}x")
    print()
    print("--- Polygon serial recovery ---")
    print(f"serial_capture_reference         : {SERIAL_CAPTURE_REFERENCE:.2f}")
    print(f"current_capture_seconds          : {capture:.2f}")
    print(f"capture_execution_mode           : {polygon.get('execution_mode','UNKNOWN')}")
    print(f"network_workers                  : {polygon.get('network_workers',0)}")
    print(f"request_count                    : {polygon.get('request_count',0)}")
    print(f"aggregate_http_seconds           : {polygon.get('aggregate_http_seconds',0)}")
    print(f"aggregate_throttle_wait          : {polygon.get('aggregate_throttle_wait_seconds',0)}")
    print()
    print("--- Dealer bulk writer ---")
    print(f"profiled_dealer_reference        : {PROFILED_DEALER_REFERENCE:.2f}")
    print(f"current_dealer_seconds           : {dealer_wall:.2f}")
    print(f"dealer_reduction_pct             : {pct(PROFILED_DEALER_REFERENCE,dealer_wall):.2f}%")
    print(f"dealer_execution_mode            : {dealer.get('execution_mode','UNKNOWN')}")
    print(f"dealer_workers                   : {dealer.get('worker_count',0)}")
    print(f"dealer_preload_seconds           : {float(dealer.get('preload_seconds',0) or 0):.4f}")
    print(f"dealer_compute_wall_seconds      : {float(dealer.get('compute_seconds',0) or 0):.4f}")
    print(f"dealer_persistence_seconds       : {float(dealer.get('persistence_seconds',0) or 0):.4f}")
    totals = dealer.get("timing_totals") or {}
    for key in ("compute_worker_seconds", "bulk_delete_seconds", "bulk_prepare_seconds", "bulk_insert_seconds", "bulk_commit_seconds"):
        print(f"dealer_{key:<27}: {float(totals.get(key,0) or 0):.4f}")
    profile = dealer.get("persistence_profile") or {}
    print(f"dealer_persistence_mode          : {profile.get('mode','UNKNOWN')}")
    print(f"dealer_summary_rows              : {profile.get('summary_rows',0)}")
    print(f"dealer_strike_rows               : {profile.get('strike_rows',0)}")
    print(f"dealer_expiration_rows           : {profile.get('expiration_rows',0)}")
    print(f"dealer_surface_rows              : {profile.get('surface_rows',0)}")
    print()
    print("--- Lineage integrity ---")
    print(f"governed_option_rows             : {metadata.get('governed_option_rows',0)}")
    print(f"valid_records                    : {metadata.get('valid_records',0)}")
    print(f"stale_daily_rows_pruned          : {metadata.get('stale_daily_rows_pruned',0)}")
    print(f"completed_successfully           : {metadata.get('completed_successfully',False)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
