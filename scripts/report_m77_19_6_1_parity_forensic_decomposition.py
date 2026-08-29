#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("reports/m77/m77_19_6_1_parity_forensic_decomposition.json")
if not p.exists(): raise SystemExit("Run M77.19.6.1 first")
x=json.loads(p.read_text())
print("=== M77.19.6.1 PARITY FORENSIC DECOMPOSITION ===")
print("forensic_conclusion:",x["forensic_conclusion"])
print("production_authority_effect:",x["production_authority_effect"])
print("\n--- PRICE INPUT PARITY ---")
q=x["price_input_parity"]
print("symbols_audited:",q["symbols_audited"])
print("common_rows:",q["common_rows"])
print("exact_ohlcv_rows:",q["exact_ohlcv_rows"])
print("exact_ohlcv_pct:",q["exact_ohlcv_pct"])
print("\n--- CADENCE DECOMPOSITION ---")
for k,v in x["cadence_error_decomposition"].items():
 print(k,v)
print("\n--- FINDINGS ---")
for f in x["findings"]: print(f)
print("\nstate_hash_semantic_markers:",len(x["state_hash_semantic_markers"]))
print("external_context_semantic_markers:",len(x["external_context_semantic_markers"]))
print("next_step:",x["next_step"])
