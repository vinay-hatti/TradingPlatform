#!/usr/bin/env python3
import json
from pathlib import Path

p=Path("reports/m77/m77_15_6_5_material_long_history_proxy_authority_certification.json")
if not p.exists():
    raise SystemExit("Run M77.15.6.5 certification first")

x=json.loads(p.read_text())
print("=== M77.15.6.5 MATERIAL LONG-HISTORY PROXY AUTHORITY CERTIFICATION ===")
print("status:",x["status"])
print("authority_type:",x["authority_type"])
print("certified_for_m77_15_7_long_history_replication:",x["certified_for_m77_15_7_long_history_replication"])
print("production_authority_effect:",x["production_authority_effect"])

print("\n--- COMMON AUTHORITY ---")
for k,v in x["common_authority"].items():
    print(f"{k}: {v}")

print("\n--- TARGETS ---")
for target,v in x["targets"].items():
    print(target,v)

print("\n--- GATES ---")
for k,v in x["gates"].items():
    print(f"{k}: {v}")

print("\n--- QQQ LINEAGE ---")
print(x["qqq_lineage"])

print("\n--- PROMOTION GOVERNANCE ---")
for k,v in x["promotion_governance"].items():
    print(f"{k}: {v}")

print("\n--- FROZEN REPLICATION ERAS ---")
for e in x["replication_era_policy"]["frozen_eras"]:
    print(e)

print("next_step:",x["next_step"])
