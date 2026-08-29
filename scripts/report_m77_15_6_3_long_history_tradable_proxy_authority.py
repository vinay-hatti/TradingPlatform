#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
M=ROOT/"research_data/m77_15_6_3/tradable_proxy_history/manifests/latest.json"

if not M.exists():
    raise SystemExit("Run M77.15.6.3 materialize first")

x=json.loads(M.read_text())
print("=== M77.15.6.3 LONG-HISTORY TRADABLE PROXY RESEARCH AUTHORITY ===")
print("status:",x["status"])
print("provider:",x["provider"])
print("authority_type:",x["authority_type"])
print("requested_range:",x["requested_range"])
print("production_authority_effect:",x["governance"]["production_authority_effect"])

print("\n--- EXPLICIT TARGET / PROXY MAPPING ---")
for target,v in x["targets"].items():
    a=v["continuity_audit"]
    print(
        target,
        "proxy=",v["research_instrument"],
        "ticker=",v["polygon_ticker"],
        "rows=",a["row_count"],
        "range=",a["first_date"],"->",a["last_date"],
        "dupes=",len(a["duplicate_dates"]),
        "ohlc_violations=",a["ohlc_violation_count"],
        "extreme_moves=",a["extreme_daily_move_count"],
        "gaps_gt4d=",a["calendar_gap_gt4d_count"],
    )

print("\n--- CROSS-PROXY SESSION AUDIT ---")
c=x["cross_symbol_session_audit"]
print("union_session_count:",c["union_session_count"])
print("common_session_count:",c["common_session_count"])
print("union_range:",c["union_first_date"],"->",c["union_last_date"])
for target,v in c["per_symbol_missing_vs_union"].items():
    print(target,"missing_vs_union=",v["count"],"sample=",v["sample"][:12])

print("\n--- GOVERNANCE ---")
for k,v in x["governance"].items():
    print(f"{k}: {v}")
print("next_step:",x["next_step"])
