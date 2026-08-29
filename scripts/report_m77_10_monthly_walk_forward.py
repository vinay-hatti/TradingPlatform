#!/usr/bin/env python3
import argparse,json
from pathlib import Path
ap=argparse.ArgumentParser()
ap.add_argument("--input",default="reports/m77/m77_10_monthly_walk_forward_certification.json")
ap.add_argument("--show-certified",action="store_true")
a=ap.parse_args()
d=json.loads(Path(a.input).read_text())
print("=== M77.10 MONTHLY MODEL REPLAY & WALK-FORWARD CERTIFICATION ===")
print("Version:",d["version"]); print("Status:",d["status"]); print("Production authority effect:",d["production_authority_effect"])
print("\n--- COVERAGE ---")
for k,v in d["coverage"].items(): print(f"{k}: {v}")
print("\n--- SUMMARY ---")
for k,v in d["summary"].items(): print(f"{k}: {v}")
print("\n--- ACCEPTANCE ---")
for k,v in d["acceptance"].items(): print(f"{k}: {v}")
if a.show_certified:
    print("\n--- CERTIFIED MONTHLY COHORTS ---")
    for x in d["cohort_certification"]:
        if x["certified"]:
            print(f'{x["horizon_sessions"]}d | {x.get("regime","UNKNOWN")} | {x["direction"]} | {x["score_band"]} | {x["confidence_band"]} | full={x["passed_full"]}/{x["selected_full"]} total={x["passed_total"]}/{x["selected_total"]}')
print("\nNext step:",d["next_step"])
