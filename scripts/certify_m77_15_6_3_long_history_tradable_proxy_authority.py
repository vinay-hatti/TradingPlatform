#!/usr/bin/env python3
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
M=ROOT/"research_data/m77_15_6_3/tradable_proxy_history/manifests/latest.json"
OUT=ROOT/"reports/m77/m77_15_6_3_tradable_proxy_authority_certification.json"

if not M.exists():
    raise SystemExit("Run M77.15.6.3 materialize first")

x=json.loads(M.read_text())
gates={}
for target,v in x["targets"].items():
    a=v["continuity_audit"]
    start_gate=v["certification_start_no_later_than"]
    min_rows=int(v["minimum_rows"])
    gates[target]={
        "research_instrument":v["research_instrument"],
        "authority_type_is_long_history_tradable_proxy":v["authority_type"]=="LONG_HISTORY_TRADABLE_PROXY",
        "starts_by_target_specific_gate":bool(a["first_date"] and a["first_date"]<=start_gate),
        "start_gate":start_gate,
        "row_count_ge_min":a["row_count"]>=min_rows,
        "minimum_rows":min_rows,
        "duplicate_dates_zero":len(a["duplicate_dates"])==0,
        "ohlc_violations_zero":a["ohlc_violation_count"]==0,
    }

bool_keys=(
    "authority_type_is_long_history_tradable_proxy",
    "starts_by_target_specific_gate",
    "row_count_ge_min",
    "duplicate_dates_zero",
    "ohlc_violations_zero",
)
all_pass=all(all(v[k] for k in bool_keys) for v in gates.values())

out={
    "version":"M77.15.6.3-TRADABLE-PROXY-AUTHORITY-CERTIFICATION-1.0",
    "status":"READY",
    "authority_type":"LONG_HISTORY_TRADABLE_PROXY",
    "gates":gates,
    "certified_for_m77_15_7_long_history_replication":all_pass,
    "promotion_governance":{
        "proxy_results_are_not_index_results":True,
        "proxy_only_survivor_may_not_advance":True,
        "future_cross_authority_same_direction_required":True,
        "canonical_recent_index_confirmation_required":True
    },
    "database_writes":False,
    "production_authority_effect":False,
    "next_step":"BUILD_M77_15_7_LONG_HISTORY_REPLICATION" if all_pass else "REVIEW_PROXY_DATA_COVERAGE_OR_SOURCE_GAPS"
}
OUT.parent.mkdir(parents=True,exist_ok=True)
tmp=OUT.with_suffix(".json.tmp")
tmp.write_text(json.dumps(out,indent=2)+"\n")
json.loads(tmp.read_text())
tmp.replace(OUT)
print(json.dumps(out,indent=2))
