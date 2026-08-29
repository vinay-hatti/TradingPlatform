#!/usr/bin/env python3
import json,argparse
from pathlib import Path
p=Path("reports/m77/m77_14_astronomical_cycle_feasibility.json")
a=argparse.ArgumentParser(); a.add_argument("--show-supported",action="store_true"); a.add_argument("--show-top",type=int,default=15); x=a.parse_args()
if not p.exists():raise SystemExit("Run M77.14 first")
r=json.loads(p.read_text())
print("=== M77.14 ASTRONOMICAL / FINANCIAL-ASTROLOGY FEASIBILITY ===")
for k in ("status","targets","result_count","research_supported_count","traditional_astrology_disposition","next_step","production_authority_effect"):print(f"{k}: {r.get(k)}")
rows=sorted(r["results"],key=lambda z:(z.get("bh_q",1),-abs((z.get("overall") or {}).get("incremental_vs_placebo_pct") or 0)))
print("\n--- TOP PRE-REGISTERED RESULTS ---")
for z in rows[:x.show_top]:
    o=z["overall"]; print(f'{z["target"]} {z["horizon_sessions"]}d {z["hypothesis"]} family={z["family"]} N={o.get("n")} mean={o.get("mean_return_pct")} inc_placebo={o.get("incremental_vs_placebo_pct")} q={z.get("bh_q"):.4g} status={z["status"]}')
if x.show_supported:
    print("\n--- RESEARCH SUPPORTED ---")
    good=[z for z in rows if z["status"]=="RESEARCH_SUPPORTED"]
    if not good:print("NONE")
    for z in good:print(z["key"],z["overall"])
