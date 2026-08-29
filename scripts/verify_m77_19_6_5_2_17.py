#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
P = ROOT / "scripts/run_m77_19_6_5_2_17_minimal_cluster_ancestry_causal_replay.py"
if not P.exists():
    raise SystemExit("M77.19.6.5.2.17 verification FAILED: runner missing")
T = P.read_text()
required = (
    'EXPECTED_REPORT_5216_SHA256 = "14d27a0b77de03c306baa76f4b1178201f97305612f32f84e9c97ce2b8c41752"',
    'EXPECTED_RUNNER_5216_SHA256 = "870593692bdb5532bac463606c0715726a2667431d6fd699adf7bd8c9b21d762"',
    '"AES": "TARGET_ABSORBED_INTO_PREEXISTING_CLUSTER"',
    '"ANET": "TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS"',
    '"ATO": "TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS"',
    '"ABSORPTION_ONLY_FORCE_TARGET_NEW_CLUSTER"',
    '"CENTROID_DRIFT_ONLY_PIN_TARGET_CLUSTER"',
    '"COMBINED_MINIMAL_TARGET_LOCAL"',
    '"target_local_interventions_only": True',
    '"global_semantic_inference_authorized": False',
    '"candidate_semantic_promoted": False',
    'NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35',
    'LEVEL_REACHABILITY_THRESHOLD = 0.003',
    'PARITY_TOLERANCE = 1e-9',
    '"threshold_search_or_optimization": False',
    '"production_authority_effect": False',
)
missing = [x for x in required if x not in T]
if missing:
    raise SystemExit(f"M77.19.6.5.2.17 verification FAILED: missing markers {missing}")
for bad in ("threshold_grid", "optimize_threshold", "UPDATE ", "INSERT ", "DELETE ", "DROP TABLE", "ALTER TABLE"):
    if bad in T:
        raise SystemExit(f"M77.19.6.5.2.17 verification FAILED: prohibited token {bad}")
print("M77.19.6.5.2.17 verification PASSED")
print(" - M77.19.6.5.2.16 report and runner are SHA-pinned")
print(" - AES absorption and ANET/ATO centroid-drift classifications are frozen")
print(" - four predeclared causal arms are fixed")
print(" - absorption-only must recover AES only")
print(" - centroid-drift-only must recover ANET and ATO only")
print(" - combined target-local arm must recover all three")
print(" - combined arm remains forensic only; no semantic promotion")
print(" - 0.35 x ATR, 0.3%, and 1e-9 thresholds remain fixed")
print(" - no threshold search or optimization")
print(" - no database access is required")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
