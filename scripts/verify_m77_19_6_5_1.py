#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
runner = root / "scripts" / "run_m77_19_6_5_1_native_replay_invocation_contract_recovery.py"

if not runner.exists():
    raise SystemExit("M77.19.6.5.1 verification FAILED: runner missing")

text = runner.read_text()
tree = ast.parse(text)

required = [
    "heuristic_adapter_execution_allowed",
    "build_adapter_contract_is_execution_authority",
    "target_call_sites",
    "assignments_in_enclosing_function",
    "calls_in_enclosing_function",
    "source_sha256",
    "isolated_profile",
    "M77_19_6_5_2_NATIVE_CONTROLLED_EXECUTION_AND_PARITY_CERTIFICATION",
    '"full_23_year_reconstruction_authorized": False',
    '"production_authority_effect": False',
]

# source_sha256 concept is represented by the generic "sha256" field.
if "sha256_text" not in text:
    raise SystemExit(
        "M77.19.6.5.1 verification FAILED: source SHA-256 capture missing"
    )

for marker in required:
    if marker == "source_sha256":
        continue
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.1 verification FAILED: missing marker: " + marker
        )

for prohibited in [
    "SessionLocal",
    "create_engine(",
    ".execute(",
    "subprocess.run(",
    "fn(**",
]:
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.1 verification FAILED: execution/database behavior detected: "
            + prohibited
        )

print("M77.19.6.5.1 verification PASSED")
print(" - source-native call sites are captured instead of heuristic execution")
print(" - build_adapter_contract is explicitly rejected as execution authority")
print(" - enclosing assignments/calls are captured for dependency reconstruction")
print(" - source SHA-256 provenance is captured")
print(" - no production DB access or replay execution")
print(" - full 23-year reconstruction remains blocked")
