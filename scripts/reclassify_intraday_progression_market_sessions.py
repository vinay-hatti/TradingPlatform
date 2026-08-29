#!/usr/bin/env python3
from pathlib import Path
import json,shutil
from intraday_market_session import market_session_info
p=Path("reports/market_ingestion/intraday_exclusion_progression/history.jsonl")
if not p.exists():
    print({"status":"NO_HISTORY","rows_reclassified":0}); raise SystemExit(0)
backup=p.with_name("history.pre_1_5_1_market_session.jsonl")
shutil.copy2(p,backup)
rows=[]; n=0
for line in p.read_text().splitlines():
    if not line.strip(): continue
    x=json.loads(line)
    info=market_session_info(x.get("source_shadow_generated_at") or x.get("generated_at"))
    if x.get("mode")=="PROSPECTIVE_EXCLUSION_BASELINE" and not info["market_session"]:
        x.update(info); x["certification_eligible"]=False
        comp=x.get("prospective_comparison") or {}
        comp["gate"]="NON_MARKET_SESSION_DIAGNOSTIC"
        comp["certification_fail_count"]=0
        comp["certification_fail_symbols"]=[]
        x["prospective_comparison"]=comp
        n+=1
    rows.append(x)
p.write_text("\n".join(json.dumps(x,default=str) for x in rows)+"\n")
print({"status":"APPLIED","rows_reclassified":n,"backup":str(backup),"production_effect":False})
