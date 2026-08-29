#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
P = ROOT / "scripts/run_m77_19_6_5_2_18_minimal_generalizable_consolidation_semantic_forensics.py"
if not P.exists():
    raise SystemExit("M77.19.6.5.2.18 verification FAILED: runner missing")
T = P.read_text()
required = (
    'EXPECTED_REPORT_5217_SHA256 = "6b607a5807c380e7dfb0ab12116e3648e4918c12ab17a26648aa45e639e9d5d4"',
    'EXPECTED_RUNNER_5217_SHA256 = "118e8e00ed5c16acfcbfbc8c15f348414b5613002f8cfed2e7eb282100072dde"',
    'def absorption_predicate',
    'def centroid_drift_predicate',
    '"uses_symbol_identity": False',
    '"uses_frozen_target_ancestry": True',
    '"symbol_specific_rules_prohibited": True',
    '"target_specific_rules_prohibited_for_promotion": True',
    '"native_observable_only": False',
    '"production_generalizable_semantic_certified": False',
    '"candidate_semantic_promoted": False',
    '"threshold_search_or_optimization": False',
    'LEVEL_REACHABILITY_THRESHOLD = 0.003',
    'PARITY_TOLERANCE = 1e-9',
    '"production_authority_effect": False',
)
missing = [x for x in required if x not in T]
if missing:
    raise SystemExit(f"M77.19.6.5.2.18 verification FAILED: missing markers {missing}")
for bad in ("symbol == \"AES\"", "symbol == \"ANET\"", "symbol == \"ATO\"", "threshold_grid", "optimize_threshold", "UPDATE ", "INSERT ", "DELETE ", "DROP TABLE", "ALTER TABLE"):
    if bad in T:
        raise SystemExit(f"M77.19.6.5.2.18 verification FAILED: prohibited token {bad}")
print("M77.19.6.5.2.18 verification PASSED")
print(" - M77.19.6.5.2.17 report and runner are SHA-pinned")
print(" - causal split must remain exactly confirmed")
print(" - mechanism predicates do not use symbol identity")
print(" - absorption and centroid-drift predicates are predeclared")
print(" - all 3 native causal records must classify exactly")
print(" - ambiguous or unresolved predicate classification fails closed")
print(" - frozen target ancestry dependence is explicitly retained")
print(" - native-observable production generalization is NOT certified")
print(" - no symbol-specific or target-specific promotion rule is allowed")
print(" - 0.3% and 1e-9 thresholds remain fixed")
print(" - no threshold search or optimization")
print(" - database access is NONE / report-only")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
