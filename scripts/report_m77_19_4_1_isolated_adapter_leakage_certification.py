#!/usr/bin/env python3
import json
from pathlib import Path
x=json.loads(Path("reports/m77/m77_19_4_1_isolated_adapter_leakage_certification.json").read_text())
print("=== M77.19.4.1 ISOLATED ADAPTER / PIT LEAKAGE CERTIFICATION ===")
print("adapter_certified_for_isolated_historical_replay:",x["adapter_certified_for_isolated_historical_replay"])
print("production_historical_replay_authorized:",x["production_historical_replay_authorized"])
for k,v in x["gates"].items():print(k,v)
print("remaining_blocker:",x["remaining_blocker"]);print("next_step:",x["next_step"]);print("production_authority_effect:",x["production_authority_effect"])
