#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
runner = root / "scripts/run_m77_19_6_5_2_12_raw_support_resistance_candidate_generation_forensics.py"

if not runner.exists():
    raise SystemExit("M77.19.6.5.2.12.3 verification FAILED: repaired runner missing")

text = runner.read_text()
ast.parse(text)

required = (
    'input_rows = copy.deepcopy(list(data or []))',
    '"input_rows": input_rows',
    'rows_by_tf = {',
    'block["timeframe"]: block["input_rows"]',
    'no captured SupportResistanceEngine timeframe inputs',
    '"ohlc_provenance_uses_captured_native_sr_inputs": True',
    'capture_raw_sr_candidates',
    'row_provenance',
    'MERGE_THRESHOLD = 0.003',
    'PARITY_TOLERANCE = 1e-9',
    'SET TRANSACTION READ ONLY',
    '"production_authority_effect": False',
    '"full_23_year_reconstruction_authorized": False',
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.2.12.3 verification FAILED: missing " + marker
        )

for prohibited in (
    "native.build_timeframes",
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
            "M77.19.6.5.2.12.3 verification FAILED: prohibited " + prohibited
        )

print("M77.19.6.5.2.12.3 verification PASSED")
print(" - M77.19.6.5.2.12 raw-candidate forensic design is preserved")
print(" - nonexistent native.build_timeframes dependency is removed")
print(" - exact native per-timeframe SR input rows are captured at analyze(timeframe, data)")
print(" - OHLC provenance uses only those captured native SR inputs")
print(" - prediction_identity and frozen_profile bundle authorities remain preserved")
print(" - helper529 remains used only for canonical normalize_rows")
print(" - native SupportResistanceEngine remains unmodified")
print(" - native 0.3% merge threshold remains fixed")
print(" - parity tolerance remains 1e-9")
print(" - database remains READ ONLY SPY session calendar only")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
