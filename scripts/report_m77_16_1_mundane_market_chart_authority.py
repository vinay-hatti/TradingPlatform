#!/usr/bin/env python3
import json
from pathlib import Path

p=Path("reports/m77/m77_16_1_mundane_market_chart_authority.json")
if not p.exists():
    raise SystemExit("Run M77.16.1 certify first")

x=json.loads(p.read_text())
print("=== M77.16.1 MUNDANE MARKET-CHART AUTHORITY ===")
print("status:",x["status"])
print("certified_for_h3_feature_materialization:",x["certified_for_h3_feature_materialization"])
print("next_step:",x["next_step"])
print("production_authority_effect:",x["production_authority_effect"])

print("\n--- MARKET CHART AUTHORITY ---")
m=x["market_chart_authority"]
print("reference_event:",m["reference_event"])
print("zodiac:",m["zodiac"])
print("ayanamsha:",m["ayanamsha"])
print("house_system:",m["house_system"])
print("node_type:",m["node_type"])

print("\n--- H3 PREREGISTRATION ---")
h=x["h3_preregistration"]
print("states:",h["states"])
print("conjunction_orb_deg:",h["conjunction_orb_deg"])
print("horizons:",h["horizons"])
print("predictions:",h["predictions"])

print("\n--- GATES ---")
for k,v in x["gates"].items():
    print(f"{k}: {v}")
