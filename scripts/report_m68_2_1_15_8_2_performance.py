from __future__ import annotations
import json
from pathlib import Path

PHASE2_OPTIONS_SECONDS = 1336.27
PHASE2_VALUATION_SECONDS = 87.4062
PHASE2_VALUATION_PRELOAD_SECONDS = 77.781498
PHASE2_DEALER_SECONDS = 232.62
PHASE2_VOLATILITY_SECONDS = 69.95
ORIGINAL_OPTIONS_SECONDS = 1585.00

def recursive_stage(node, key):
    if isinstance(node, dict):
        stages = node.get("stages")
        if isinstance(stages, dict) and isinstance(stages.get(key), dict):
            return stages[key]
        for value in node.values():
            found = recursive_stage(value, key)
            if found is not None: return found
    elif isinstance(node, list):
        for value in node:
            found = recursive_stage(value, key)
            if found is not None: return found
    return None

def pct(before, after):
    return ((before-after)/before*100.0) if before else 0.0

def main():
    root = Path(__file__).resolve().parents[1]
    finalization = json.loads((root / "reports/market_ingestion/options_finalization_latest.json").read_text())
    lifecycle = json.loads((root / "reports/market_ingestion/options_lifecycle_latest.json").read_text())
    dealer = json.loads((root / "reports/market_ingestion/dealer_positioning_latest.json").read_text())
    valuation = recursive_stage(finalization, "option_valuation") or {}
    profile = valuation.get("parallel_profile") or {}
    current = float(lifecycle.get("elapsed_seconds") or 0)
    if not current:
        raise RuntimeError("Run one governed options cycle after M68.2.1.15.8.2 first.")
    current_valuation = float(valuation.get("duration_seconds") or 0)
    current_preload = float(profile.get("preload_seconds") or 0)
    print("=== M68.2.1.15.8.2 PERFORMANCE ===")
    print(f"phase2_options_seconds       : {PHASE2_OPTIONS_SECONDS:.2f}")
    print(f"current_options_seconds      : {current:.2f}")
    print(f"phase2_time_saved_seconds    : {PHASE2_OPTIONS_SECONDS-current:.2f}")
    print(f"phase2_reduction_pct         : {pct(PHASE2_OPTIONS_SECONDS,current):.2f}%")
    print(f"cumulative_vs_original_pct   : {pct(ORIGINAL_OPTIONS_SECONDS,current):.2f}%")
    print(f"cumulative_speedup           : {ORIGINAL_OPTIONS_SECONDS/current:.3f}x")
    print()
    print("--- Valuation preload ---")
    print(f"phase2_valuation_seconds     : {PHASE2_VALUATION_SECONDS:.4f}")
    print(f"current_valuation_seconds    : {current_valuation:.4f}")
    print(f"phase2_preload_seconds       : {PHASE2_VALUATION_PRELOAD_SECONDS:.6f}")
    print(f"current_preload_seconds      : {current_preload:.6f}")
    print(f"coherent_market_seconds      : {float(profile.get('coherent_market_preload_seconds') or 0):.6f}")
    print(f"valuation_preload_reduction  : {pct(PHASE2_VALUATION_PRELOAD_SECONDS,current_preload):.2f}%")
    print()
    print("--- Dealer profile ---")
    print(f"phase2_dealer_seconds        : {PHASE2_DEALER_SECONDS:.2f}")
    print(f"dealer_preload_seconds       : {float(dealer.get('preload_seconds') or 0):.4f}")
    print(f"dealer_execution_seconds     : {float(dealer.get('execution_seconds') or 0):.4f}")
    print(f"dealer_execution_mode        : {dealer.get('execution_mode','UNKNOWN')}")
    print(f"dealer_worker_count          : {dealer.get('worker_count',0)}")
    print()
    print("Reference phase2 volatility : %.2fs" % PHASE2_VOLATILITY_SECONDS)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
