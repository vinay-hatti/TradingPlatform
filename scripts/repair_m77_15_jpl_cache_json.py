#!/usr/bin/env python3
from pathlib import Path
import json,shutil

CACHE=Path("reports/m77/m77_15_0_jpl_ephemeris_cache")
if not CACHE.exists():
    print({"status":"NO_CACHE_DIRECTORY","production_effect":False})
    raise SystemExit(0)

examined=repaired=valid=0
for p in sorted(CACHE.glob("*.json")):
    examined+=1
    raw=p.read_text()
    try:
        json.loads(raw)
        valid+=1
        continue
    except json.JSONDecodeError:
        pass
    cleaned=raw
    while cleaned.endswith("\\n"):
        cleaned=cleaned[:-2]
    cleaned=cleaned.rstrip()
    try:
        obj=json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: {p} malformed beyond known literal-backslash-n suffix defect: {exc}")
    backup=p.with_name(p.name+".pre_m77_15_1_3")
    shutil.copy2(p,backup)
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(obj,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(p)
    repaired+=1

print({"status":"APPLIED","cache_files_examined":examined,"already_valid":valid,"repaired":repaired,"production_effect":False})
