#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("reports/m77/m77_17_2_astrology_research_closure.json")
if not p.exists(): raise SystemExit("Run M77.17.2 close first")
x=json.loads(p.read_text())
print("=== M77.17.2 ASTROLOGY RESEARCH CLOSURE ===")
print("status:",x["status"])
print("production_authority_effect:",x["production_authority_effect"])
print("\n--- CLOSURE ---")
for k,v in x["closure"].items(): print(k,v)
print("\n--- M77.17 EVIDENCE ---")
for k,v in x["m77_17_evidence"].items(): print(f"{k}: {v}")
print("\n--- RETIREMENT ---")
for k,v in x["retirement"].items(): print(f"{k}: {v}")
print("\n--- CERTIFICATION ---")
for k,v in x["certification"].items(): print(f"{k}: {v}")
print("next_step:",x["next_step"])
