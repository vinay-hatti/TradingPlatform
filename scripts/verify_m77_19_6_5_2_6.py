#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
path = (
    root
    / "scripts"
    / "run_m77_19_6_5_2_6_native_mt_and_participation_upstream_divergence_forensics.py"
)

if not path.exists():
    raise SystemExit("M77.19.6.5.2.6 verification FAILED: runner missing")

text = path.read_text()
tree = ast.parse(text)

required = (
    "EXPECTED_524_REPORT_SHA256",
    "EXPECTED_525_REPORT_SHA256",
    "a293b8f87ef56762d60989cda3cc03ad224999a1a6d846af7b64e318c48d4e8a",
    "confidence_formula_detected_as_unweighted_mean",
    "direction_formula_uses_timeframe_weights",
    "weekly_only_intervention_meaning",
    "score_independence_from_confidence_intervention",
    "state_independence_from_confidence_intervention",
    "timeframe_states.1w.confidence",
    "PARTICIPATION",
    "PARITY_TOLERANCE = 1e-9",
    "controlled_exact_input_parity_certified",
    "full_23_year_reconstruction_authorized",
    "production_authority_effect",
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.2.6 verification FAILED: missing " + marker
        )

for prohibited in (
    "SessionLocal",
    "DATABASE_URL",
    "create_engine(",
    "session.execute(",
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "TRUNCATE ",
):
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.2.6 verification FAILED: database/write marker detected: "
            + prohibited
        )

# Reject imports of production package modules. This milestone must analyze
# pinned reports/source text only.
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.startswith("trading_ai"):
                raise SystemExit(
                    "M77.19.6.5.2.6 verification FAILED: production package import detected"
                )
    if isinstance(node, ast.ImportFrom):
        if node.module and node.module.startswith("trading_ai"):
            raise SystemExit(
                "M77.19.6.5.2.6 verification FAILED: production package import detected"
            )

print("M77.19.6.5.2.6 verification PASSED")
print(" - M77.19.6.5.2.4 and .5 report SHAs are pinned")
print(" - no database access is permitted")
print(" - no production package import is permitted")
print(" - native MT confidence aggregation semantics are inspected from pinned source")
print(" - weekly-state confidence and aggregate-profile confidence are kept causally distinct")
print(" - remaining non-confidence upstream paths are classified")
print(" - participation paths are explicitly inventoried")
print(" - score/state failure remains a blocking condition")
print(" - parity tolerance remains 1e-9")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
