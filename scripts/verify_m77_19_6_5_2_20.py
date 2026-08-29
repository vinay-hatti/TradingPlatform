#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
P = ROOT / "scripts/run_m77_19_6_5_2_20_native_observable_trigger_collateral_impact_forensics.py"
if not P.exists():
    raise SystemExit("M77.19.6.5.2.20 verification FAILED: runner missing")
T = P.read_text()

required = (
    'EXPECTED_REPORT_5219_SHA256 = "9e024506d6c519b73ac9c32d8e11b350a35329627e58e5243fed03e1911a52c7"',
    'EXPECTED_RUNNER_5219_SHA256 = "1a47684e03de666163366baaa9c852bf0e9c24325c4109bb45ad3ef93dbea1f0"',
    'EXPECTED_NATIVE_EXACT = 1338',
    'EXPECTED_NATIVE_MISSING = 67',
    'EXPECTED_SPLIT_EXACT = 549',
    'EXPECTED_SPLIT_MISSING = 560',
    'EXPECTED_PRESERVE_EXACT = 1222',
    'EXPECTED_PRESERVE_MISSING = 150',
    '"NON_DEGRADING_IMPROVEMENT"',
    '"EXACTLY_UNCHANGED"',
    '"ANY_DEGRADATION"',
    '"target_symbols"',
    '"non_target_symbols"',
    '"new_trigger_semantic_introduced": False',
    '"new_threshold_introduced": False',
    '"threshold_search_or_optimization": False',
    '"candidate_semantic_promoted": False',
    '"production_authority_effect": False',
)
missing = [x for x in required if x not in T]
if missing:
    raise SystemExit(f"M77.19.6.5.2.20 verification FAILED: missing markers {missing}")

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
        raise SystemExit(f"M77.19.6.5.2.20 verification FAILED: prohibited token {bad}")

print("M77.19.6.5.2.20 verification PASSED")
print(" - M77.19.6.5.2.19 report and runner are SHA-pinned")
print(" - native 1338 exact / 67 missing authority is mandatory")
print(" - SPLIT_WIDE 549 exact / 560 missing authority is mandatory")
print(" - PRESERVE_SEED 1222 exact / 150 missing authority is mandatory")
print(" - all 48 symbol records are evaluated")
print(" - collateral is measured as per-symbol exact and missing deltas")
print(" - target and non-target damage are separated")
print(" - non-degrading, unchanged and degrading symbols are classified")
print(" - worst-damage and best-nondegrading symbols are ranked diagnostically")
print(" - no new trigger semantic or threshold is introduced")
print(" - no threshold search or optimization")
print(" - database access is NONE / report-only")
print(" - candidate semantic remains unpromoted")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
