#!/usr/bin/env python3
from pathlib import Path
import json, shutil

DIR=Path("reports/m77/m77_14_3_lunar_forward_shadow")
H=DIR/"history.jsonl"
L=DIR/"latest.json"
PARTIAL="FIRST_QUARTER_WINDOW:2026-08-19"

if not H.exists():
    print({"status":"NO_HISTORY","rows_updated":0,"production_effect":False})
    raise SystemExit(0)

backup=DIR/"history.pre_m77_14_3_1.jsonl"
shutil.copy2(H,backup)
rows=[]
updated=0
for line in H.read_text().splitlines():
    if not line.strip():
        continue
    x=json.loads(line)
    if x.get("episode_id")==PARTIAL:
        x["episode_eligibility"]="PARTIAL_LAUNCH_EPISODE"
        x["counts_toward_review_gate"]=False
        updated+=1
    rows.append(x)
H.write_text("\n".join(json.dumps(x,default=str) for x in rows)+"\n")

if L.exists():
    x=json.loads(L.read_text())
    if x.get("episode_id")==PARTIAL:
        x["episode_eligibility"]="PARTIAL_LAUNCH_EPISODE"
        x["counts_toward_review_gate"]=False
        L.write_text(json.dumps(x,indent=2,default=str)+"\n")

print({"status":"APPLIED","rows_updated":updated,"backup":str(backup),"production_effect":False})
