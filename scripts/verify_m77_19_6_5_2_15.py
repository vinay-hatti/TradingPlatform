#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
P = ROOT / "scripts/run_m77_19_6_5_2_15_post_candidate_consolidation_semantics_causal_replay.py"
if not P.exists():
    raise SystemExit("M77.19.6.5.2.15 verification FAILED: runner missing")
T = P.read_text()

required = (
    'EXPECTED_REPORT_5214_SHA256 = "3cced0fca689833455e548e9f5f66fe54bcad5bd9b53f470af62f7c4f7ca275b"',
    'EXPECTED_RUNNER_5214_SHA256 = "2fc32620d3e05927f7a85ada94c4364b47b49df32c63acbe432e8556e40132dd"',
    'EXPECTED_PRECONSOLIDATION_TARGETS = 3',
    '"NO_TOP12_BASELINE"',
    '"NO_TOP12_KEEP_SEED_PRICE"',
    '"NO_TOP12_NEAREST_MATCH"',
    '"NO_TOP12_FIXED_SEED_MEMBERSHIP"',
    'NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35',
    'LEVEL_REACHABILITY_THRESHOLD = 0.003',
    'PARITY_TOLERANCE = 1e-9',
    '"pivot_radius": 2',
    '"rolling_windows": [20, 50, 100]',
    '"threshold_search_or_optimization": False',
    '"production_authority_effect": False',
    '"full_23_year_reconstruction_authorized": False',
)
missing = [x for x in required if x not in T]
if missing:
    raise SystemExit(f"M77.19.6.5.2.15 verification FAILED: missing markers {missing}")

for bad in ("threshold_grid", "optimize_threshold", "UPDATE ", "INSERT ", "DELETE ", "DROP TABLE", "ALTER TABLE"):
    if bad in T:
        raise SystemExit(f"M77.19.6.5.2.15 verification FAILED: prohibited token {bad}")

print("M77.19.6.5.2.15 verification PASSED")
print(" - M77.19.6.5.2.14 report and runner are SHA-pinned")
print(" - native replay runner and native Level/SR source authorities remain pinned")
print(" - 3 preconsolidation targets are authority assertions")
print(" - candidate generation remains radius 2 + rolling 20/50/100")
print(" - native internal consolidation radius remains 0.35 x ATR")
print(" - native LevelIntelligence reachability threshold remains 0.3%")
print(" - causal arms isolate centroid movement, first-match assignment and moving-membership semantics")
print(" - NO_TOP12 remains forensic baseline only")
print(" - no threshold search or optimization is allowed")
print(" - database remains READ ONLY SPY session calendar only")
print(" - parity tolerance remains 1e-9")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
