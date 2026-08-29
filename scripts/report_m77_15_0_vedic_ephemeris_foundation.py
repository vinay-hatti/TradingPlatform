#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("reports/m77/m77_15_0_ephemeris_foundation_parity.json")
if not p.exists(): raise SystemExit("Run M77.15.0 parity first")
x=json.loads(p.read_text())
print("=== M77.15.0 VEDIC EPHEMERIS FOUNDATION ===")
for k in ("status","authoritative_provider","authoritative_state_count","next_step","production_authority_effect"): print(f"{k}: {x.get(k)}")
print("\n--- ACCEPTANCE ---")
for k,v in x["acceptance"].items(): print(f"{k}: {v}")
p=x["diagnostic_candidate_parity"]
print("\n--- LOW-PRECISION ENGINE DIAGNOSTIC PARITY ---")
print("comparisons:",p["comparisons"]); print("mean_angular_error_deg:",p["mean_angular_error_deg"]); print("max_angular_error_deg:",p["max_angular_error_deg"]); print("disposition:",p["disposition"])
for r in p["rows"]: print(r["date"],r["body"],"JPL=",round(r["jpl_tropical_longitude_deg"],6),"candidate=",round(r["existing_m77_14_low_precision_deg"],6),"error_deg=",round(r["angular_error_deg"],6))
print("\nSidereal/Rashi/Nakshatra/Tithi materialization remains fail-closed until Lahiri parity.")
