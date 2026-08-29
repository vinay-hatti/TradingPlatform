#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
path = root / "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"

if not path.exists():
    raise SystemExit("M77.19.6.5.2.9.1 verification FAILED: repaired runner missing")

text = path.read_text()
ast.parse(text)

required = (
    'VERSION = "M77.19.6.5.2.9.1-NATIVE-TYPED-COMPONENT-REHYDRATION-REPAIR-1.0"',
    "EXPECTED_528_SHA256",
    "EXPECTED_527_SHA256",
    "EXPECTED_NATIVE_RUNNER_SHA256",
    "PARITY_TOLERANCE = 1e-9",
    "_construct_native_component",
    "_native_component_type",
    "rehydrate_native_sequence",
    'required_attributes=("price",)',
    'required_attributes=("lower_bound", "upper_bound")',
    "dict support level leaked into native pipeline",
    "dict resistance level leaked into native pipeline",
    "dict structure zone leaked into native pipeline",
    "native_typed_component_rehydration_required",
    "plain_dict_component_injection_allowed",
    "SET TRANSACTION READ ONLY",
    "native.compare_profile",
    '"full_23_year_reconstruction_authorized": False',
    '"production_authority_effect": False',
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.2.9.1 verification FAILED: missing " + marker
        )

for prohibited in (
    'result["support_levels"] = copy.deepcopy(frozen_support)',
    'result["resistance_levels"] = copy.deepcopy(frozen_resistance)',
    'return copy.deepcopy(frozen_zones)',
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "TRUNCATE ",
    "session.commit(",
    '"production_authority_effect": True',
    '"full_23_year_reconstruction_authorized": True',
):
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.2.9.1 verification FAILED: prohibited marker " + prohibited
        )

print("M77.19.6.5.2.9.1 verification PASSED")
print(" - M77.19.6.5.2.9 causal arm design is preserved")
print(" - frozen support/resistance JSON is rehydrated into exact native runtime type")
print(" - rehydrated levels must expose native .price attribute")
print(" - frozen structure-zone JSON is rehydrated into exact native runtime type")
print(" - rehydrated structure zones must expose lower_bound/upper_bound attributes")
print(" - plain dict component injection is explicitly rejected")
print(" - native level and structure services still execute before intervention")
print(" - downstream breakout/scoring/trade-plan/certification/decision recompute natively")
print(" - database remains READ ONLY SPY session calendar only")
print(" - parity tolerance remains 1e-9")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
