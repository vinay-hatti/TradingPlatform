#!/usr/bin/env python3
import argparse,json
from pathlib import Path

ap=argparse.ArgumentParser()
ap.add_argument("--input",default="reports/m77/m77_11_multi_cadence_confluence_conflict_study.json")
ap.add_argument("--show-supported",action="store_true")
ap.add_argument("--show-evidence",action="store_true")
a=ap.parse_args()
d=json.loads(Path(a.input).read_text())

print("=== M77.11 DAILY × WEEKLY × MONTHLY CONFLUENCE / CONFLICT STUDY ===")
print("Version:",d["version"])
print("Status:",d["status"])
print("Production authority effect:",d["production_authority_effect"])
print("\n--- COVERAGE ---")
for k,v in d["coverage"].items(): print(f"{k}: {v}")
print("\n--- COMPONENT CERTIFICATION ---")
for k,v in d["component_certification"].items(): print(f"{k}: {v}")
print("\n--- SUMMARY ---")
for k,v in d["summary"].items(): print(f"{k}: {v}")

if a.show_supported:
    print("\n--- RESEARCH-SUPPORTED CONFLUENCE / CONFLICT CLASSES ---")
    if not d["research_supported"]:
        print("NONE")
    for x in d["research_supported"]:
        print(f'{x["horizon_sessions"]}d | {x["class"]} | full={x["full_years_passed"]}/{x["full_years"]} partial={x["partial_years_passed"]}/{x["partial_years"]}')

if a.show_evidence:
    print("\n--- YEARLY INCREMENTAL EVIDENCE ---")
    for e in d["evidence"]:
        if e["pass"]:
            print(f'{e["year"]} {e["year_credit"]} | {e["horizon_sessions"]}d | {e["class"]} | '
                  f'N={e["group"]["n"]} mean={e["group"]["mean_pct"]:+.3f}% hit={e["group"]["hit_rate_pct"]:.2f}% '
                  f'inc={e["incremental_vs_best_component_pct"]:+.3f}% PASS')

print("\nNext step:",d["next_step"])
