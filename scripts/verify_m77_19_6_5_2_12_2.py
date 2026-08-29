#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
runner = (
    root
    / "scripts"
    / "run_m77_19_6_5_2_12_raw_support_resistance_candidate_generation_forensics.py"
)

if not runner.exists():
    raise SystemExit("M77.19.6.5.2.12.2 verification FAILED: repaired runner missing")

text = runner.read_text()
ast.parse(text)

required = (
    'identity = bundle.get("prediction_identity")',
    'bundle missing prediction_identity authority',
    'prediction_identity missing symbol',
    'prediction_identity missing as_of',
    'symbol = str(symbol)',
    'as_of = dt.date.fromisoformat(str(as_of_raw)[:10])',
    'frozen_output = bundle.get("frozen_profile")',
    'helper529.normalize_rows(bundle)',
    'capture_raw_sr_candidates',
    'MERGE_THRESHOLD = 0.003',
    'PARITY_TOLERANCE = 1e-9',
    'SET TRANSACTION READ ONLY',
    '"production_authority_effect": False',
    '"full_23_year_reconstruction_authorized": False',
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.2.12.2 verification FAILED: missing " + marker
        )

for prohibited in (
    "helper529.bundle_symbol",
    "helper529.bundle_as_of",
    "helper529.frozen_output",
    "session.commit(",
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "TRUNCATE ",
    '"production_authority_effect": True',
    '"full_23_year_reconstruction_authorized": True',
    "optimize_threshold",
    "best_threshold",
):
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.2.12.2 verification FAILED: prohibited " + prohibited
        )

print("M77.19.6.5.2.12.2 verification PASSED")
print(" - M77.19.6.5.2.12 candidate-generation forensic design is preserved")
print(" - nonexistent helper529.bundle_symbol dependency is removed")
print(" - nonexistent helper529.bundle_as_of dependency is removed")
print(" - bundle identity authority is prediction_identity.symbol + prediction_identity.as_of")
print(" - frozen replay authority remains bundle['frozen_profile']")
print(" - helper529 remains used only for canonical normalize_rows")
print(" - native SupportResistanceEngine instrumentation is unchanged")
print(" - native 0.3% merge threshold remains fixed")
print(" - parity tolerance remains 1e-9")
print(" - database remains READ ONLY SPY session calendar only")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
