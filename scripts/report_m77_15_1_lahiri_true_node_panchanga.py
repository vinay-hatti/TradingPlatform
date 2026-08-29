#!/usr/bin/env python3
import json
from pathlib import Path
cert=Path("reports/m77/m77_15_1_lahiri_true_node_parity.json")
panch=Path("reports/m77/m77_15_1_panchanga_foundation.json")
if not cert.exists(): raise SystemExit("Run M77.15.1 parity first")
x=json.loads(cert.read_text())
print("=== M77.15.1 LAHIRI / TRUE-NODE / PANCHANGA FOUNDATION ===")
print("acceptance:",x["acceptance"]); print("next_step:",x["next_step"])
print("\n--- PARITY ROWS ---")
for r in x["rows"]:
    print(r["date"],"ayan_err_deg=",round(r["lahiri_error_deg"],8),"node_err_deg=",round(r["true_node_error_deg"],8))
if panch.exists():
    y=json.loads(panch.read_text())
    print("\n--- PANCHANGA FOUNDATION SAMPLE ---")
    for r in y["rows"]:
        print(r["date"],"Moon",r["moon_rashi"]["name"],r["moon_nakshatra"]["name"],"Pada",r["moon_nakshatra"]["pada"],
              "Tithi",r["tithi"]["number"],r["tithi"]["paksha"],"Yoga",r["yoga"]["name"],"Karana",r["karana"]["name"],
              "Rahu",round(r["rahu_true_node_deg"],4),"Ketu",round(r["ketu_deg"],4))
