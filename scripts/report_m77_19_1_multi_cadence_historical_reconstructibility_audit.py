#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("reports/m77/m77_19_1_multi_cadence_historical_reconstructibility_audit.json")
if not p.exists():
    raise SystemExit("Run M77.19.1 first")
x = json.loads(p.read_text())

print("=== M77.19.1 MULTI-CADENCE HISTORICAL RECONSTRUCTIBILITY AUDIT ===")
print("status:", x["status"])
print("exact_long_history_reconstruction_authorized:", x["exact_long_history_reconstruction_authorized"])
print("production_authority_effect:", x["production_authority_effect"])
print("\n--- ORIGINAL UNIVERSE / PRICE COVERAGE ---")
for k, v in x["historical_universe_and_price_coverage"].items():
    print(f"{k}: {v}")
print("\n--- GATES ---")
for k, v in x["gates"].items():
    print(f"{k}: {v}")
print("\n--- BLOCKERS ---")
for b in x["blockers"]:
    print(b)
print("\n--- RUNNER DISCOVERY ---")
for kind, rows in x["runner_discovery"].items():
    print(kind)
    for row in rows:
        print(" ", row)
print("\n--- INTERPRETATION ---")
print(x["interpretation"])
print("next_step:", x["next_step"])
