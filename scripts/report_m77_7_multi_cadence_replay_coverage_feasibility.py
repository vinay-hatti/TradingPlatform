#!/usr/bin/env python3
import argparse,json
from pathlib import Path

ap=argparse.ArgumentParser()
ap.add_argument(
    "--input",
    default="reports/m77/m77_7_multi_cadence_replay_coverage_feasibility.json",
)
ap.add_argument("--show-gaps",action="store_true")
a=ap.parse_args()
d=json.loads(Path(a.input).read_text())

print("=== M77.7 MULTI-CADENCE REPLAY COVERAGE & FEASIBILITY ===")
print("Version:",d["version"])
print("Source:",d["source"])
print()
print("--- COVERAGE ---")
for k,v in d["coverage_summary"].items():
    print(f"{k}: {v}")
print()
print("--- FEASIBILITY ---")
for k,v in d["feasibility"].items():
    print(f"{k}: {v}")
print()
print("--- CONTEXT ---")
for k,v in d["context_feasibility"].items():
    print(f"{k}: {v}")
if a.show_gaps:
    print()
    print("--- GAPS ---")
    for x in d["gaps"]:
        print(f'{x["severity"]}: {x["gap"]}')
        print(f'  {x["remediation"]}')
print()
print("Existing weekly M77 mutation: NONE")
print("Production authority effect: NONE")
