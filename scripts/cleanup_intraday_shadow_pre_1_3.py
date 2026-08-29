#!/usr/bin/env python3
from pathlib import Path
import json, shutil
p=Path("reports/market_ingestion/intraday_active_universe_shadow/history.jsonl")
latest=Path("reports/market_ingestion/intraday_active_universe_shadow/latest.json")
if not p.exists():
    print({"status":"NO_HISTORY","removed":0}); raise SystemExit(0)
rows=p.read_text().splitlines()
bad=[]; keep=[]
for line in rows:
    try:
        x=json.loads(line)
        if x.get("version") in {"INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.0","INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.1","INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.2"}:
            bad.append(line)
        else: keep.append(line)
    except Exception: keep.append(line)
backup=p.with_suffix(".pre_1_3.jsonl")
shutil.copy2(p,backup)
p.write_text(("\n".join(keep)+"\n") if keep else "")
if latest.exists():
    try:
        x=json.loads(latest.read_text())
        if x.get("version") in {"INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.0","INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.1","INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.2"}: latest.unlink()
    except Exception: pass
print({"status":"APPLIED","invalid_shadow_rows_removed":len(bad),"backup":str(backup),"production_effect":False})
