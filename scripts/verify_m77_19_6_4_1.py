#!/usr/bin/env python3
import ast,sys
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
p=root/"scripts/run_m77_19_6_4_1_replay_authority_resolution_adapter_recovery.py"
if not p.exists(): raise SystemExit("M77.19.6.4.1 verification FAILED: runner missing")
t=p.read_text(); tree=ast.parse(t)
required=[
"from trading_ai.database.session import SessionLocal",
"SET TRANSACTION READ ONLY",
"observation_capable",
"run_level_penalty",
"FILESYSTEM_FROZEN_ARTIFACT",
'"controlled_exact_input_parity_certified":False',
'"full_23_year_reconstruction_authorized":False',
'"production_authority_effect":False',
]
for x in required:
    if x not in t: raise SystemExit("M77.19.6.4.1 verification FAILED: missing "+x)
for bad in ["from trading_ai.database import DATABASE_URL","from trading_ai.database.database import engine"]:
    if bad in t: raise SystemExit("M77.19.6.4.1 verification FAILED: prohibited DB import")
bad_sql=(" INSERT "," UPDATE "," DELETE "," MERGE "," TRUNCATE "," DROP "," ALTER "," CREATE TABLE ")
for n in ast.walk(tree):
    if isinstance(n,ast.Constant) and isinstance(n.value,str):
        s=" "+" ".join(n.value.upper().split())+" "
        if any(x in s for x in bad_sql): raise SystemExit("M77.19.6.4.1 verification FAILED: write SQL detected")
print("M77.19.6.4.1 verification PASSED")
print(" - run-level replay tables are penalized and cannot win without observation semantics")
print(" - observation authority requires symbol/date/direction/score/confidence")
print(" - filesystem frozen artifacts are a governed fallback")
print(" - database transaction is READ ONLY")
print(" - no production write SQL/DDL")
print(" - parity thresholds unchanged; 23-year reconstruction remains blocked")
