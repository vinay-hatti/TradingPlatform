#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("reports/m77/m77_19_3_isolated_harness_foundation.json")
if not p.exists():
    raise SystemExit("Run M77.19.3 certify first")
x = json.loads(p.read_text())

print("=== M77.19.3 ISOLATED DAILY/MONTHLY/PIT HARNESS FOUNDATION ===")
print("status:", x["status"])
print("harness_foundation_certified:", x["harness_foundation_certified"])
print("historical_replay_execution_authorized:", x["historical_replay_execution_authorized"])
print("production_authority_effect:", x["production_authority_effect"])

print("\n--- GATES ---")
for k, v in x["gates"].items():
    print(f"{k}: {v}")

print("\n--- SOURCE CALLABLES ---")
for k, v in x["source_analysis"].items():
    print(k, v["path"], "sha256=", v.get("sha256"))
    for f in v.get("top_level_functions", []):
        print(" ", f)

print("\n--- REMAINING BLOCKERS ---")
for b in x["remaining_blockers"]:
    print(b)

print("next_step:", x["next_step"])
