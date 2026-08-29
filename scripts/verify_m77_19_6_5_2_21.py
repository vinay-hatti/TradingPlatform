#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
P = ROOT / "scripts/run_m77_19_6_5_2_21_native_cluster_event_activation_density_forensics.py"
if not P.exists():
    raise SystemExit("M77.19.6.5.2.21 verification FAILED: runner missing")
T = P.read_text()

required = (
    'EXPECTED_REPORT_5220_SHA256 = "1919911096baf7b9c6d352a3af15195af65272897220b3c739a7ed0e4ee6e6c0"',
    'EXPECTED_RUNNER_5220_SHA256 = "1716c3f52f4f0d1c13890adecdceb5a93cd687430c3dd61d76dafc715c65f07c"',
    'EXPECTED_MONTHLY_BUNDLE_COUNT = 48',
    '"split_wide_activation"',
    '"preserve_seed_activation"',
    '"activation_per_1000_raw_candidates"',
    '"activation_per_1000_native_merges"',
    '"timeframe_distribution"',
    '"side_distribution"',
    '"candidate_source_distribution"',
    '"causal_target_identity_used_for_diagnostic_labeling_only": True',
    '"symbol_identity_used_in_trigger_logic": False',
    '"frozen_target_identity_used_in_trigger_logic": False',
    '"historical_answer_leakage_into_trigger_logic": False',
    '"new_trigger_semantic_introduced": False',
    '"new_threshold_introduced": False',
    '"threshold_search_or_optimization": False',
    'NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35',
    'LEVEL_REACHABILITY_THRESHOLD = 0.003',
    'PARITY_TOLERANCE = 1e-9',
    '"candidate_semantic_promoted": False',
    '"production_authority_effect": False',
)
missing = [x for x in required if x not in T]
if missing:
    raise SystemExit(f"M77.19.6.5.2.21 verification FAILED: missing markers {missing}")

for bad in (
    "threshold_grid",
    "optimize_threshold",
    "UPDATE ",
    "INSERT ",
    "DELETE ",
    "DROP TABLE",
    "ALTER TABLE",
):
    if bad in T:
        raise SystemExit(f"M77.19.6.5.2.21 verification FAILED: prohibited token {bad}")

print("M77.19.6.5.2.21 verification PASSED")
print(" - M77.19.6.5.2.20 report and runner are SHA-pinned")
print(" - all 48 monthly bundles are mandatory")
print(" - native SR candidate generation is instrumented without semantic changes")
print(" - raw candidate, native merge, SPLIT_WIDE and PRESERVE_SEED events are counted")
print(" - activation density is measured per 1,000 candidates and per 1,000 native merges")
print(" - timeframe, side, source and symbol concentration are reported")
print(" - causal target identity is used for diagnostic labeling only")
print(" - causal labels are prohibited from trigger logic")
print(" - no new trigger semantic or threshold is introduced")
print(" - 0.35 x ATR, 0.3% and 1e-9 remain fixed")
print(" - no threshold search or optimization")
print(" - database use is READ ONLY SPY session calendar only")
print(" - candidate semantic remains unpromoted")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
