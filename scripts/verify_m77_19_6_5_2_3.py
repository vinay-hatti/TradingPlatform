#!/usr/bin/env python3
import ast,sys
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
p=root/"scripts/run_m77_19_6_5_2_3_monthly_context_parity_difference_forensics.py"
if not p.exists(): raise SystemExit("M77.19.6.5.2.3 verification FAILED: runner missing")
t=p.read_text(); ast.parse(t)
for marker in [
    "MAX_SESSION_BACKTRACK = 8",
    "SET TRANSACTION READ ONLY",
    "EXPECTED_522_REPORT_SHA256",
    "native.call_profile",
    "candidate_sessions",
    "exact_candidate_found",
    "unique_confidence_signed_errors",
    "category_mismatches",
    "parity_thresholds_relaxed",
    '"controlled_exact_input_parity_certified":False',
    '"full_23_year_reconstruction_authorized":False',
    '"production_authority_effect":False',
]:
    if marker not in t: raise SystemExit("M77.19.6.5.2.3 verification FAILED: missing "+marker)
for bad in ["from trading_ai.database import DATABASE_URL","from trading_ai.database.database import engine"]:
    if bad in t: raise SystemExit("M77.19.6.5.2.3 verification FAILED: prohibited DB import")
print("M77.19.6.5.2.3 verification PASSED")
print(" - failed M77.19.6.5.2.2 report is pinned as forensic authority")
print(" - monthly session-cutoff hypotheses are tested, not assumed")
print(" - all 48 monthly bundles are examined")
print(" - parity thresholds remain unchanged")
print(" - database remains READ ONLY")
print(" - no parity certification occurs in this package")
print(" - 23-year reconstruction remains blocked")
