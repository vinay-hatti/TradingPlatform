#!/usr/bin/env python3
import json
from pathlib import Path

p=Path("reports/m77/m77_19_6_isolated_replay_engine_parity_certification.json")
if not p.exists(): raise SystemExit("Run M77.19.6 certify first")
x=json.loads(p.read_text())

print("=== M77.19.6 ISOLATED REPLAY ENGINE PARITY CERTIFICATION ===")
print("isolated_replay_engine_parity_certified:",x["isolated_replay_engine_parity_certified"])
print("full_23_year_reconstruction_authorized:",x["full_23_year_reconstruction_authorized"])
print("production_authority_effect:",x["production_authority_effect"])

for cadence,v in x["cadence_results"].items():
    print(f"\n--- {cadence} ---")
    print("comparisons:",v["comparisons"])
    print("direction_match_pct:",v["direction_match_pct"])
    print("state_hash_match_pct:",v["state_hash_match_pct"])
    print("max_score_abs_error:",v["max_score_abs_error"])
    print("max_confidence_abs_error:",v["max_confidence_abs_error"])
    print("deterministic_repeat_pct:",v["deterministic_repeat_pct"])
    print("pass:",v["pass"])
    print("errors:",len(v["errors"]))
    for k,g in v["gates"].items(): print(k,g)

print("\ninterpretation:",x["interpretation"])
print("next_step:",x["next_step"])
