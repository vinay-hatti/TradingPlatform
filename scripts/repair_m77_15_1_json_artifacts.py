#!/usr/bin/env python3
from pathlib import Path
import json
import shutil

FILES=(
    Path("reports/m77/m77_15_1_lahiri_true_node_parity.json"),
    Path("reports/m77/m77_15_1_panchanga_foundation.json"),
)

for p in FILES:
    if not p.exists():
        print({"path":str(p),"status":"NOT_PRESENT","production_effect":False})
        continue

    raw=p.read_text()
    try:
        json.loads(raw)
        print({"path":str(p),"status":"ALREADY_VALID","production_effect":False})
        continue
    except json.JSONDecodeError:
        pass

    cleaned=raw
    literal_suffix_count=0
    while cleaned.endswith("\\n"):
        cleaned=cleaned[:-2]
        literal_suffix_count+=1
    cleaned=cleaned.rstrip()

    try:
        obj=json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"ERROR: {p} is malformed beyond the known literal-backslash-n suffix defect: {exc}"
        )

    backup=p.with_name(p.name+".pre_m77_15_1_2")
    shutil.copy2(p,backup)
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(obj,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(p)

    print({
        "path":str(p),
        "status":"REPAIRED_LITERAL_BACKSLASH_N_SUFFIX",
        "literal_suffix_count":literal_suffix_count,
        "backup":str(backup),
        "production_effect":False,
    })
