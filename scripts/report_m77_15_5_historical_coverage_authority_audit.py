#!/usr/bin/env python3
import json
from pathlib import Path

p=Path("reports/m77/m77_15_5_historical_coverage_authority_audit.json")
if not p.exists():
    raise SystemExit("Run M77.15.5 audit first")

x=json.loads(p.read_text())
print("=== M77.15.5 HISTORICAL COVERAGE & RESEARCH AUTHORITY AUDIT ===")
print("status:",x["status"])
print("next_step:",x["next_step"])
print("production_authority_effect:",x["production_authority_effect"])

print("\n--- PIT REGIME COVERAGE ---")
pit=x["audit"]["pit_regime_coverage"]
print("rows:",pit["rows"])
print("first_date:",pit["first_date"])
print("last_date:",pit["last_date"])

print("\n--- TARGET PRICE COVERAGE ---")
for target,detail in x["audit"]["targets"].items():
    c=detail["price_coverage"]
    print(target,c)

print("\n--- EVENT FAMILY COVERAGE BY TARGET ---")
for target,detail in x["audit"]["targets"].items():
    print(f"\n[{target}]")
    for fam,row in detail["event_family_coverage"].items():
        print(
            f"{fam:<34} "
            f"astro={row['astronomical_event_count']:<4} "
            f"price_overlap={row['price_overlap_event_count']:<4} "
            f"pit_exact_date_overlap={row['pit_exact_date_overlap_event_count']:<4}"
        )

print("\n--- RECOMMENDED RESEARCH AUTHORITY SPLIT ---")
for k,v in x["recommendation"].items():
    print(f"{k}: {v}")
