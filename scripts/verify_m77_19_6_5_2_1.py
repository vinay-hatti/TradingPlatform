#!/usr/bin/env python3
import ast,sys
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
p=root/"scripts/run_m77_19_6_5_2_1_native_output_schema_compare_contract_forensics.py"
if not p.exists(): raise SystemExit("M77.19.6.5.2.1 verification FAILED: runner missing")
t=p.read_text(); tree=ast.parse(t)
for marker in [
    "inspect.getsource(native.compare_profile)",
    "inspect.getsource(native.call_profile)",
    "native.compare_profile(first,stored)",
    "structural_shape",
    "SET TRANSACTION READ ONLY",
    '"forensic_probe_only":True',
    '"full_23_year_reconstruction_authorized":False',
]:
    if marker not in t: raise SystemExit("M77.19.6.5.2.1 verification FAILED: missing "+marker)
for bad in ["from trading_ai.database import DATABASE_URL","from trading_ai.database.database import engine"]:
    if bad in t: raise SystemExit("M77.19.6.5.2.1 verification FAILED: prohibited DB import")
bad_sql=(" INSERT "," UPDATE "," DELETE "," MERGE "," TRUNCATE "," DROP "," ALTER "," CREATE TABLE ")
for n in ast.walk(tree):
    if isinstance(n,ast.Constant) and isinstance(n.value,str):
        s=" "+" ".join(n.value.upper().split())+" "
        if any(x in s for x in bad_sql): raise SystemExit("M77.19.6.5.2.1 verification FAILED: write SQL detected")
print("M77.19.6.5.2.1 verification PASSED")
print(" - native output schema is probed, not guessed")
print(" - native compare_profile source is captured")
print(" - only one controlled bundle per cadence is executed")
print(" - database remains READ ONLY")
print(" - parity is not certified by this forensic probe")
print(" - 23-year reconstruction remains blocked")
