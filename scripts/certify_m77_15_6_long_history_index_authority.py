#!/usr/bin/env python3
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
M=ROOT/"research_data/m77_15_6/index_history/manifests/latest.json"
OUT=ROOT/"reports/m77/m77_15_6_long_history_authority_certification.json"

MIN_START="2000-01-10"
MIN_ROWS={"SPX":6000,"NDX":6000,"RUT":6000}
MAX_DUPES=0
MAX_OHLC_VIOLATIONS=0

if not M.exists():
    raise SystemExit("Run M77.15.6 materialize first")
x=json.loads(M.read_text())

gates={}
for sym,min_rows in MIN_ROWS.items():
    v=x["targets"].get(sym)
    if not v:
        gates[sym]={"present":False}
        continue
    a=v["continuity_audit"]
    gates[sym]={
        "present":True,
        "starts_by_2000_01_10":bool(a["first_date"] and a["first_date"]<=MIN_START),
        "row_count_ge_min":a["row_count"]>=min_rows,
        "duplicate_dates_zero":len(a["duplicate_dates"])==MAX_DUPES,
        "ohlc_violations_zero":a["ohlc_violation_count"]==MAX_OHLC_VIOLATIONS,
    }

all_pass=all(all(v.values()) for v in gates.values())
out={
    "version":"M77.15.6-LONG-HISTORY-AUTHORITY-CERTIFICATION-1.0",
    "status":"READY",
    "gates":gates,
    "certified_for_m77_15_7_replication":all_pass,
    "production_authority_effect":False,
    "database_writes":False,
    "next_step":"BUILD_M77_15_7_LONG_HISTORY_REPLICATION" if all_pass else "REVIEW_DATA_COVERAGE_OR_SOURCE_GAPS"
}
OUT.parent.mkdir(parents=True,exist_ok=True)
tmp=OUT.with_suffix(".json.tmp")
tmp.write_text(json.dumps(out,indent=2)+"\n")
json.loads(tmp.read_text())
tmp.replace(OUT)
print(json.dumps(out,indent=2))
