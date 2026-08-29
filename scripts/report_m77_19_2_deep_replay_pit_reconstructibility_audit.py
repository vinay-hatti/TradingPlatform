#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("reports/m77/m77_19_2_deep_replay_pit_reconstructibility_audit.json")
if not p.exists():
    raise SystemExit("Run M77.19.2 first")
x = json.loads(p.read_text())

print("=== M77.19.2 DEEP REPLAY/PIT RECONSTRUCTIBILITY AUDIT ===")
print("status:", x["status"])
print("exact_long_history_reconstruction_authorized:", x["exact_long_history_reconstruction_authorized"])
print("production_authority_effect:", x["production_authority_effect"])

print("\n--- GATES ---")
for k, v in x["gates"].items():
    print(f"{k}: {v}")

print("\n--- BLOCKERS ---")
for b in x["blockers"]:
    print(b)

print("\n--- SOURCE ANALYSIS ---")
for name, a in x["source_analysis"].items():
    print(f"\n[{name}] {a.get('path')}")
    for k in (
        "exists",
        "argparse_options",
        "explicit_historical_range_parameterization",
        "mentions_point_in_time_semantics",
        "mentions_future_sensitive_tokens",
        "mentions_database_write_tokens",
        "mentions_production_namespaces",
        "mentions_historical_namespace"
    ):
        print(f"  {k}: {a.get(k)}")

print("\n--- REQUIRED ISOLATION CONTRACT ---")
for k, v in x["required_isolation_contract"].items():
    print(f"{k}: {v}")

print("next_step:", x["next_step"])
