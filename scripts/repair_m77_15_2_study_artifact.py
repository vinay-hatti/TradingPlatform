#!/usr/bin/env python3
from pathlib import Path
import json, shutil

OUT=Path("reports/m77/m77_15_2_single_factor_panchanga_study.json")
TMP=OUT.with_suffix(".json.tmp")

def clean_legacy(raw):
    cleaned=raw
    while cleaned.endswith("\\n"):
        cleaned=cleaned[:-2]
    return cleaned.rstrip()

if OUT.exists():
    try:
        json.loads(OUT.read_text())
        print({"status":"FINAL_ALREADY_VALID","production_effect":False})
        raise SystemExit(0)
    except json.JSONDecodeError:
        pass

if not TMP.exists():
    print({"status":"NO_REPAIRABLE_TEMP_ARTIFACT","rerun_required":True,"production_effect":False})
    raise SystemExit(0)

raw=TMP.read_text()
try:
    obj=json.loads(raw)
except json.JSONDecodeError:
    obj=json.loads(clean_legacy(raw))

OUT.parent.mkdir(parents=True,exist_ok=True)
if OUT.exists():
    backup=OUT.with_name(OUT.name+".pre_m77_15_2_1")
    shutil.copy2(OUT,backup)
else:
    backup=None

fixed=OUT.with_suffix(OUT.suffix+".tmp")
fixed.write_text(json.dumps(obj,indent=2,default=str)+"\n")
json.loads(fixed.read_text())
fixed.replace(OUT)
TMP.unlink(missing_ok=True)

print({
    "status":"RECOVERED_FROM_FAILED_TEMP_ARTIFACT",
    "result_count":obj.get("result_count"),
    "research_supported_candidate_count":obj.get("research_supported_candidate_count"),
    "backup":str(backup) if backup else None,
    "rerun_required":False,
    "production_effect":False,
})
