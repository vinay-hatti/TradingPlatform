#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("data/m77/m77_16_2_h3_house_features_2000_2040.metadata.json")
if not p.exists(): raise SystemExit("Run M77.16.2 materialize first")
x=json.loads(p.read_text())
print("=== M77.16.2 H3 HOUSE/LORDSHIP FEATURE MATERIALIZATION ===")
for k in ("status","rows","first_date","last_date","fifth_house_lord","eleventh_house_lord","max_node_opposition_error_deg","certified_for_h3_financial_study","next_step","production_authority_effect"):
    print(f"{k}: {x.get(k)}")
print("\n--- REFERENCE CHART ---"); print(x["reference_chart"])
print("\n--- FEATURE COUNTS ---")
for k,v in x["feature_counts"].items(): print(f"{k}: {v}")
print("\n--- GATES ---")
for k,v in x["gates"].items(): print(f"{k}: {v}")
