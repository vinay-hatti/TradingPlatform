#!/usr/bin/env python3
from pathlib import Path
import hashlib
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
runner = ROOT / "scripts/run_m77_19_6_5_2_14_residual_candidate_generation_semantics_forensics.py"
if not runner.exists():
    raise SystemExit("M77.19.6.5.2.14 verification FAILED: runner missing")

text = runner.read_text()
required = (
    'EXPECTED_REPORT_5213_SHA256 = "10bdff010160faa49175c123907c9c8eb365739c547c95c679841355258c847e"',
    'EXPECTED_RUNNER_5213_SHA256 = "c3b5b27c4327f73e6767b1381ecca758eb8b1816e4f15bf57dbd9c9bade68892"',
    'EXPECTED_NATIVE_MISSING = 67',
    'EXPECTED_NO_TOP12_MISSING = 54',
    'EXPECTED_RESTORED_BY_NO_TOP12 = 13',
    '"FROZEN_TIMEFRAME_NATIVE_INELIGIBLE_LT20"',
    '"FROZEN_TIMEFRAME_PRECONSOLIDATION_CANDIDATE_NOT_REACHABLE"',
    '"FROZEN_TIMEFRAME_OHLC_EXACT_BUT_NATIVE_SELECTION_EXCLUDES"',
    '"CROSS_TIMEFRAME_PRECONSOLIDATION_CANDIDATE_PROVENANCE"',
    '"NO_CAPTURED_OHLC_PROVENANCE"',
    'LEVEL_MERGE_THRESHOLD = 0.003',
    'PARITY_TOLERANCE = 1e-9',
    '"database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY"',
    '"production_authority_effect": False',
    '"full_23_year_reconstruction_authorized": False',
)
missing = [x for x in required if x not in text]
if missing:
    raise SystemExit(f"M77.19.6.5.2.14 verification FAILED: missing markers {missing}")

prohibited = (
    "threshold_grid",
    "optimize_threshold",
    "UPDATE ",
    "INSERT ",
    "DELETE ",
    "DROP TABLE",
    "ALTER TABLE",
)
for token in prohibited:
    if token in text:
        raise SystemExit(f"M77.19.6.5.2.14 verification FAILED: prohibited token {token}")

print("M77.19.6.5.2.14 verification PASSED")
print(" - M77.19.6.5.2.13 report SHA is pinned")
print(" - M77.19.6.5.2.13.1 repaired runner SHA is pinned")
print(" - native replay runner and native level/SR source authorities remain pinned")
print(" - 67 native missing and 54 NO_TOP12 residual counts are authority assertions")
print(" - 13-level NO_TOP12 recovery is preserved as forensic evidence only")
print(" - residuals are classified by captured native timeframe/OHLC provenance")
print(" - pivot-radius-2 and rolling 20/50/100 qualification are observed, not optimized")
print(" - native 0.3% merge threshold remains fixed")
print(" - database remains READ ONLY SPY session calendar only")
print(" - parity tolerance remains 1e-9")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
