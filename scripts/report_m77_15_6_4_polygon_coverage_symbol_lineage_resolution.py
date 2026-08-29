#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
M=ROOT/"research_data/m77_15_6_4/polygon_coverage_lineage/manifests/latest.json"

if not M.exists():
    raise SystemExit("Run M77.15.6.4 diagnostic first")

x=json.loads(M.read_text())
print("=== M77.15.6.4 POLYGON COVERAGE & SYMBOL-LINEAGE RESOLUTION ===")
print("status:",x["status"])
print("provider:",x["provider"])
print("requested_range:",x["requested_range"])
print("production_authority_effect:",x["governance"]["production_authority_effect"])

print("\n--- RAW SYMBOL COVERAGE ---")
for sym,v in x["source_series"].items():
    print(sym,"rows=",v["rows"],"range=",v["first_date"],"->",v["last_date"])

print("\n--- QQQ LINEAGE ---")
q=x["qqq_lineage"]
print("segments:",q["frozen_segments"])
print("stitched_range:",
      q["stitched_continuity_audit"]["first_date"],"->",
      q["stitched_continuity_audit"]["last_date"],
      "rows=",q["stitched_continuity_audit"]["row_count"])
print("stitched_dupes=",len(q["stitched_continuity_audit"]["duplicate_dates"]))
print("stitched_ohlc_violations=",q["stitched_continuity_audit"]["ohlc_violation_count"])

print("\n--- FINDINGS ---")
for k,v in x["findings"].items():
    print(k,v)

print("\n--- GOVERNANCE ---")
for k,v in x["governance"].items():
    print(f"{k}: {v}")
print("next_step:",x["next_step"])
