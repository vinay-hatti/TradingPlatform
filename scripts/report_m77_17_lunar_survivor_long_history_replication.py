#!/usr/bin/env python3
import json
from pathlib import Path

p=Path("reports/m77/m77_17_lunar_survivor_long_history_replication.json")
if not p.exists(): raise SystemExit("Run M77.17 replication first")
x=json.loads(p.read_text())
print("=== M77.17 LUNAR SURVIVOR LONG-HISTORY REPLICATION ===")
for k in ("status","primary_replication_target","primary_replication_pass","all_three_same_framework_pass","disposition","production_authority_effect"):
    print(f"{k}: {x.get(k)}")
print("authority:",x["authority"])
print("frozen_survivor:",x["frozen_survivor"])
for target,r in x["results"].items():
    print(f"\n--- {target} / {r['instrument']} ---")
    for k in ("event_n","event_mean_absolute_return","complement_mean_absolute_return","incremental_vs_complement",
              "incremental_vs_weekday_month","dependence_robust_empirical_p","bootstrap_ci95",
              "nonoverlap_event_n","nonoverlap_incremental","replication_pass"):
        print(f"{k}: {r.get(k)}")
    print("gates:")
    for k,v in r["gates"].items(): print(f"  {k}: {v}")
    print("eras:")
    for e in r["era_stats"]: print(" ",e)
