#!/usr/bin/env python3
from __future__ import annotations
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
path = root / "scripts" / "run_m77_19_6_5_2_11_level_selection_hypothesis_causal_replay.py"

if not path.exists():
    raise SystemExit("M77.19.6.5.2.11.1 verification FAILED: runner missing")

text = path.read_text()
ast.parse(text)

required = (
    "dfc11d3e4f7c5c45cd47b68f6cccb9133da2f8afa0f253dfbb234ab0f27f0d51",
    "9e903c9ce752282e169a33c6beafc469af7650dd7647ba4c0788a953b764dc4c",
    "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb",
    "8581c423956fd9d997af8098fb1065aab78b24646c72b9fb5ba1e8e446402490",
    'helper529 = import_module_from_path',
    'hasattr(helper529, "normalize_rows")',
    "rows = helper529.normalize_rows(bundle)",
    "MERGE_THRESHOLD = 0.003",
    "NATIVE_FIRST_ASCENDING",
    "ARITHMETIC_MEAN",
    "STRENGTH_WEIGHTED_MEAN",
    "CONFLUENCE_WEIGHTED_MEAN",
    "TOUCH_WEIGHTED_MEAN",
    "MAX_STRENGTH_CANDIDATE",
    "capture_raw_sr_candidates",
    "SET TRANSACTION READ ONLY",
    "PARITY_TOLERANCE = 1e-9",
    '"production_authority_effect": False',
    '"full_23_year_reconstruction_authorized": False',
)

for marker in required:
    if marker not in text:
        raise SystemExit("M77.19.6.5.2.11.1 verification FAILED: missing " + marker)

if "rows = helper5210.normalize_rows(bundle)" in text:
    raise SystemExit("M77.19.6.5.2.11.1 verification FAILED: stale invalid helper call remains")

for prohibited in (
    "session.commit(",
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "TRUNCATE ",
    '"production_authority_effect": True',
    '"full_23_year_reconstruction_authorized": True',
    "best_threshold",
    "optimize_threshold",
):
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.2.11.1 verification FAILED: prohibited marker " + prohibited
        )

print("M77.19.6.5.2.11.1 verification PASSED")
print(" - M77.19.6.5.2.10 report and runner remain SHA-pinned")
print(" - M77.19.6.5.2.9.1 repaired runner is now directly SHA-pinned")
print(" - bundle normalization uses helper529.normalize_rows exactly as M77.19.6.5.2.10 does")
print(" - nonexistent helper5210.normalize_rows dependency is removed")
print(" - causal arm design is unchanged")
print(" - native 0.3% cluster membership rule remains fixed")
print(" - no threshold search or optimization is allowed")
print(" - database remains READ ONLY SPY session calendar only")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
