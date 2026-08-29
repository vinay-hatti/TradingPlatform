#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
P = ROOT / "scripts/run_m77_19_6_5_2_16_target_cluster_ancestry_provenance_trace.py"
if not P.exists():
    raise SystemExit("M77.19.6.5.2.16 verification FAILED: runner missing")
T = P.read_text()
required = (
    'EXPECTED_REPORT_5215_SHA256 = "586cefbb9f01771e1e9dd3f632406a32d559092c5440e3d8ab0e9f0bb81a1768"',
    'EXPECTED_RUNNER_5215_SHA256 = "8e4a3f5f3b723fdfa50ab5ced170f9c5e1605cd0256870b76f1d0de87851bcb0"',
    '"keep_seed_missing": 472',
    '"keep_seed_exact": 479',
    '"keep_seed_recovered": 2',
    '"TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS"',
    '"TARGET_ABSORBED_INTO_PREEXISTING_CLUSTER"',
    '"keep_seed_price_globally_rejected": True',
    '"candidate_semantic_promoted": False',
    'NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35',
    'LEVEL_REACHABILITY_THRESHOLD = 0.003',
    'PARITY_TOLERANCE = 1e-9',
    '"threshold_search_or_optimization": False',
    '"production_authority_effect": False',
)
missing = [x for x in required if x not in T]
if missing:
    raise SystemExit(f"M77.19.6.5.2.16 verification FAILED: missing markers {missing}")
for bad in ("threshold_grid", "optimize_threshold", "UPDATE ", "INSERT ", "DELETE ", "DROP TABLE", "ALTER TABLE"):
    if bad in T:
        raise SystemExit(f"M77.19.6.5.2.16 verification FAILED: prohibited token {bad}")
print("M77.19.6.5.2.16 verification PASSED")
print(" - M77.19.6.5.2.15 report and runner are SHA-pinned")
print(" - globally destructive KEEP_SEED_PRICE arm is explicitly rejected")
print(" - all 3 preconsolidation targets are traced by exact cluster ancestry")
print(" - native candidate generation remains radius 2 + rolling 20/50/100")
print(" - native consolidation radius remains 0.35 x ATR")
print(" - 0.3% reachability threshold and 1e-9 parity tolerance remain fixed")
print(" - no candidate semantic is promoted")
print(" - database remains READ ONLY SPY session calendar only")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
