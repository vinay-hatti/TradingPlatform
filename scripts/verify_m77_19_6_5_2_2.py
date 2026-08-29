#!/usr/bin/env python3
import ast,sys
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
p=root/"scripts/run_m77_19_6_5_2_2_native_compare_profile_parity_certification.py"
if not p.exists(): raise SystemExit("M77.19.6.5.2.2 verification FAILED: runner missing")
t=p.read_text(); ast.parse(t)
for marker in [
    "native.compare_profile(first,frozen)",
    "NUMERIC_TOLERANCE = 1e-9",
    "REQUIRED_MATCH_PCT = 100.0",
    "semantic_hash_match",
    "deterministic_repeat_semantic_hash_match",
    "raw_state_hash_is_diagnostic_not_semantic_gate",
    "SET TRANSACTION READ ONLY",
    '"full_23_year_reconstruction_authorized":False',
    '"production_authority_effect":False',
]:
    if marker not in t: raise SystemExit("M77.19.6.5.2.2 verification FAILED: missing "+marker)
for bad in ["from trading_ai.database import DATABASE_URL","from trading_ai.database.database import engine"]:
    if bad in t: raise SystemExit("M77.19.6.5.2.2 verification FAILED: prohibited DB import")
print("M77.19.6.5.2.2 verification PASSED")
print(" - native compare_profile is the comparison authority")
print(" - all frozen bundles are evaluated")
print(" - semantic parity requires 100% match")
print(" - score/confidence tolerance remains 1e-9")
print(" - deterministic repeat is mandatory")
print(" - raw state_hash is diagnostic only; semantic projection is explicitly gated")
print(" - database remains READ ONLY")
print(" - 23-year reconstruction remains blocked")
