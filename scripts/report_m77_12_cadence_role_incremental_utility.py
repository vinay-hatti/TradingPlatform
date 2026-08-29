#!/usr/bin/env python3
import argparse,json
from pathlib import Path

ap=argparse.ArgumentParser()
ap.add_argument("--input",default="reports/m77/m77_12_cadence_role_incremental_utility_certification.json")
ap.add_argument("--show-supported",action="store_true")
ap.add_argument("--show-passing-years",action="store_true")
a=ap.parse_args()
d=json.loads(Path(a.input).read_text())

print("=== M77.12 CADENCE ROLE & INCREMENTAL UTILITY CERTIFICATION ===")
print("Version:",d["version"])
print("Status:",d["status"])
print("Production authority effect:",d["production_authority_effect"])

print("\n--- COVERAGE ---")
for k,v in d["coverage"].items():print(f"{k}: {v}")

print("\n--- SUMMARY ---")
for k,v in d["summary"].items():print(f"{k}: {v}")

print("\n--- FROZEN BASELINES ---")
print("Daily:",len(d["frozen_baselines"]["daily"]))
print("Monthly:",len(d["frozen_baselines"]["monthly"]))
print("Monthly neutral excluded from directional overlay:",len(d["frozen_baselines"]["monthly_neutral_excluded_from_directional_overlay"]))

if a.show_supported:
    print("\n--- RESEARCH-SUPPORTED ROLE UTILITIES ---")
    if not d["research_supported"]:print("NONE")
    for x in d["research_supported"]:
        print(f'{x["baseline_source"]} | {x["baseline_id"]} | secondary={x["secondary_cadence"]} | role={x["role"]} | full={x["full_years_passed"]}/{x["full_years"]} partial={x["partial_years_passed"]}/{x["partial_years"]}')

if a.show_passing_years:
    print("\n--- PASSING YEARLY ROLE EVIDENCE ---")
    for e in d["evidence"]:
        if e["pass"]:
            s=e["role_subset"]; b=e["frozen_baseline"]
            print(f'{e["year"]} {e["year_credit"]} | {e["baseline_source"]} | {e["baseline_id"]} | '
                  f'secondary={e["secondary_cadence"]} role={e["role"]} | '
                  f'N={s["n"]} mean={s["mean_pct"]:+.3f}% hit={s["hit_rate_pct"]:.2f}% '
                  f'base={b["mean_pct"]:+.3f}% inc={e["incremental_vs_same_frozen_baseline_pct"]:+.3f}% PASS')

print("\nNext step:",d["next_step"])
