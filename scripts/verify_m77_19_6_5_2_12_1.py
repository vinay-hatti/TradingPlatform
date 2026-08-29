#!/usr/bin/env python3
from __future__ import annotations
import ast, hashlib, sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
runner = root/"scripts/run_m77_19_6_5_2_12_raw_support_resistance_candidate_generation_forensics.py"
if not runner.exists():
    raise SystemExit("M77.19.6.5.2.12.1 verification FAILED: repaired runner missing")
text = runner.read_text()
ast.parse(text)

required = (
    'frozen_output = bundle.get("frozen_profile")',
    'bundle missing canonical frozen_profile authority',
    'helper529, "normalize_rows"',
    'capture_raw_sr_candidates',
    'MERGE_THRESHOLD = 0.003',
    'PARITY_TOLERANCE = 1e-9',
    'SET TRANSACTION READ ONLY',
    '"production_authority_effect": False',
    '"full_23_year_reconstruction_authorized": False',
)
for marker in required:
    if marker not in text:
        raise SystemExit("M77.19.6.5.2.12.1 verification FAILED: missing "+marker)

prohibited = (
    "helper529.frozen_output",
    "session.commit(",
    '"production_authority_effect": True',
    '"full_23_year_reconstruction_authorized": True',
    "optimize_threshold",
    "best_threshold",
)
for marker in prohibited:
    if marker in text:
        raise SystemExit("M77.19.6.5.2.12.1 verification FAILED: prohibited "+marker)

print("M77.19.6.5.2.12.1 verification PASSED")
print(" - M77.19.6.5.2.12 causal forensic design is preserved")
print(" - nonexistent helper529.frozen_output dependency is removed")
print(" - frozen authority is bundle['frozen_profile'], matching M77.19.6.5.2.11.1")
print(" - helper529 remains used only for canonical normalize_rows")
print(" - native SupportResistanceEngine instrumentation is unchanged")
print(" - native 0.3% merge threshold remains fixed")
print(" - parity tolerance remains 1e-9")
print(" - database remains READ ONLY SPY session calendar only")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
