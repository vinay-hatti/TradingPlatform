#!/usr/bin/env python3
from pathlib import Path
import sys, shutil

target=Path(sys.argv[1] if len(sys.argv)>1 else "/Users/vinay.hatti/TradingPlatform")
p=target/"scripts/m77_forward_shadow/run_combined_forward_shadow.sh"
if not p.exists():
    raise SystemExit(f"ERROR: combined M77 forward-shadow orchestrator not found: {p}")

s=p.read_text()
marker="# BEGIN M77.14.3.1 LUNAR VOLATILITY SHADOW"
if marker in s:
    print({"status":"ALREADY_PATCHED","path":str(p)})
    raise SystemExit(0)

backup=p.with_name(p.name+".pre_m77_14_3_1")
shutil.copy2(p,backup)

block='''\n# BEGIN M77.14.3.1 LUNAR VOLATILITY SHADOW
echo "[$(date)] RUN M77.14.3 prospective lunar volatility shadow" | tee -a "$LOG_FILE"
if ! "${UV_BIN}" run python scripts/run_m77_14_3_prospective_lunar_volatility_shadow.py cycle >> "$LOG_FILE" 2>&1; then
  echo "[$(date)] DEGRADED M77.14.3 lunar shadow failed; production effect=NONE" | tee -a "$LOG_FILE"
fi
# END M77.14.3.1 LUNAR VOLATILITY SHADOW
'''
needle='END combined M77 forward-shadow orchestration'
idx=s.rfind(needle)
if idx==-1:
    s=s.rstrip()+"\n"+block+"\n"
else:
    line_start=s.rfind("\n",0,idx)+1
    s=s[:line_start]+block+s[line_start:]
p.write_text(s)
print({"status":"APPLIED","path":str(p),"backup":str(backup)})
