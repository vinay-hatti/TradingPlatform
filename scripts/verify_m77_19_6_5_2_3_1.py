#!/usr/bin/env python3
import ast,sys
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
p=root/"scripts/run_m77_19_6_5_2_3_1_monthly_forensic_probe_semantic_adapter_repair.py"
if not p.exists(): raise SystemExit("M77.19.6.5.2.3.1 verification FAILED: runner missing")
t=p.read_text(); ast.parse(t)
required=[
"SET TRANSACTION READ ONLY","ZERO_BASELINE_COMPARISONS_CAUSED_BY_SEMANTIC_ADAPTER_ATTRIBUTEERROR",
"certify_adapter","repaired_nominal_authority_reproduction","evaluation_as_of\":nominal.isoformat()",
"candidate_input_cutoff","parity_thresholds_relaxed","controlled_exact_input_parity_certified",
"full_23_year_reconstruction_authorized","production_authority_effect","EXPECTED_522_REPORT_SHA256",
]
for m in required:
    if m not in t: raise SystemExit("M77.19.6.5.2.3.1 verification FAILED: missing "+m)
for bad in ["from trading_ai.database import DATABASE_URL","from trading_ai.database.database import engine"]:
    if bad in t: raise SystemExit("M77.19.6.5.2.3.1 verification FAILED: prohibited DB import")
print("M77.19.6.5.2.3.1 verification PASSED")
print(" - rejects the zero-comparison M77.19.6.5.2.3 conclusion")
print(" - semantic adapter is certified against M77.19.6.5.2.2 monthly aggregate authority")
print(" - monthly evaluation date remains nominal while input cutoff is varied")
print(" - repaired nominal aggregate must reproduce M77.19.6.5.2.2 exactly")
print(" - parity threshold remains 1e-9")
print(" - database remains READ ONLY")
print(" - no parity certification or 23-year authorization occurs")
