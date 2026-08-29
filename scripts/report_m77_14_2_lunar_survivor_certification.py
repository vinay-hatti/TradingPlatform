#!/usr/bin/env python3
import json
from pathlib import Path

p=Path("reports/m77/m77_14_2_lunar_survivor_certification.json")
if not p.exists():
    raise SystemExit("Run M77.14.2 first")

x=json.loads(p.read_text())
print("=== M77.14.2 LUNAR SURVIVOR DEPENDENCE-ROBUST CERTIFICATION ===")
print("status:",x["status"])
print("frozen_survivor:",x["frozen_survivor"])
print("certification_disposition:",x["certification_disposition"])
print("next_step:",x["next_step"])
print("production_authority_effect:",x["production_authority_effect"])

print("\n--- OVERALL ---")
print(json.dumps(x["overall"],indent=2))

print("\n--- DEPENDENCE-ROBUST NULL ---")
print(json.dumps(x["dependence_robust_null"],indent=2))

print("\n--- CLUSTER BOOTSTRAP ---")
print(json.dumps(x["cluster_bootstrap"],indent=2))

print("\n--- NON-OVERLAP SENSITIVITY ---")
print(json.dumps(x["nonoverlap_sensitivity"],indent=2))

print("\n--- YEARLY INCREMENTAL ---")
for y,v in x["yearly_incremental"].items():
    print(y,json.dumps(v,sort_keys=True))

print("\n--- REGIME INCREMENTAL ---")
for r,v in x["regime_incremental"].items():
    print(r,json.dumps(v,sort_keys=True))

print("\n--- RESEARCH GATE ---")
for k,v in x["research_gate"].items():
    print(f"{k}: {v}")
