#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("reports/m77/m77_18_historical_depth_replication_authority_audit.json")
if not p.exists(): raise SystemExit("Run M77.18 audit first")
x=json.loads(p.read_text())
print("=== M77.18 HISTORICAL DEPTH & REPLICATION AUTHORITY AUDIT ===")
for k in ("status","files_examined","milestones_found","next_step","production_authority_effect"):
    print(f"{k}: {x.get(k)}")
print("long_history_authority:",x["long_history_authority"])
print("\n--- REPLICATION BACKLOG ---")
if not x["replication_backlog"]: print("NONE")
for b in x["replication_backlog"]:
    print(b["milestone"],b["classification"],b["priority"])
    for f in b["sample_files"]: print("  ",f)
print("\n--- CYCLE / SEASONALITY FINDINGS ---")
print(x["cycle_seasonality_findings"])
print("\n--- ALL M77 MILESTONES ---")
for ms,s in x["milestone_summary"].items():
    print(ms,s["classification"],"files=",s["file_count"],"classes=",s["class_counts"])
