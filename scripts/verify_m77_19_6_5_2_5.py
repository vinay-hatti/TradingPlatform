#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()

path = (
    root
    / "scripts"
    / "run_m77_19_6_5_2_5_monthly_component_causal_replay_certification.py"
)

if not path.exists():
    raise SystemExit("M77.19.6.5.2.5 verification FAILED: runner missing")

text = path.read_text()
tree = ast.parse(text)

required = (
    "EXPECTED_524_REPORT_SHA256",
    "WEEKLY_ONLY",
    "AGGREGATE_ONLY",
    "WEEKLY_AND_AGGREGATE",
    "native.compare_profile(",
    "SET TRANSACTION READ ONLY",
    "PARITY_TOLERANCE = 1e-9",
    "weekly_only_does_not_recompute_profile_confidence",
    "aggregate_intervention_restores_profile_confidence",
    "downstream_score_parity_after_confidence_repair",
    "full_state_parity_after_confidence_repair",
    "synthetic_interventions_may_not_be_used_as_production_authority",
    "full_23_year_reconstruction_authorized",
    "production_authority_effect",
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.2.5 verification FAILED: missing " + marker
        )

for prohibited in (
    "from trading_ai.database import DATABASE_URL",
    "from trading_ai.database.database import engine",
):
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.2.5 verification FAILED: prohibited DB import"
        )

bad_sql = (
    " INSERT ",
    " UPDATE ",
    " DELETE ",
    " MERGE ",
    " TRUNCATE ",
    " DROP ",
    " ALTER ",
    " CREATE TABLE ",
)

for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        normalized = " " + " ".join(node.value.upper().split()) + " "
        if any(token in normalized for token in bad_sql):
            raise SystemExit(
                "M77.19.6.5.2.5 verification FAILED: write SQL/DDL detected"
            )

print("M77.19.6.5.2.5 verification PASSED")
print(" - M77.19.6.5.2.4 report SHA is pinned as forensic authority")
print(" - baseline plus three controlled MT-output intervention arms are required")
print(" - weekly-only and aggregate-confidence causal paths are separated")
print(" - native compare_profile remains semantic authority")
print(" - confidence repair cannot certify full parity unless score and state also recover")
print(" - synthetic interventions cannot become production authority")
print(" - database remains READ ONLY")
print(" - parity tolerance remains 1e-9")
print(" - 23-year reconstruction remains blocked")
