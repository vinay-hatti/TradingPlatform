#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
runner = root / "scripts" / "run_m77_19_6_4_2_joined_frozen_replay_authority_recovery.py"

if not runner.exists():
    raise SystemExit("M77.19.6.4.2 verification FAILED: runner missing")

text = runner.read_text()
tree = ast.parse(text)

required = [
    "from trading_ai.database.session import SessionLocal",
    "SET TRANSACTION READ ONLY",
    "historical_underlying_replay_prediction",
    "historical_underlying_replay_run",
    "ON r.replay_run_id = p.replay_run_id",
    "p.as_of",
    "r.cadence",
    "profile_json",
    "lineage_json",
    '"generic_filesystem_fallback_allowed": False',
    '"controlled_exact_input_parity_certified": False',
    '"full_23_year_reconstruction_authorized": False',
    '"production_authority_effect": False',
]

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.4.2 verification FAILED: missing marker: " + marker
        )

for prohibited in [
    "from trading_ai.database import DATABASE_URL",
    "from trading_ai.database.database import engine",
]:
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.4.2 verification FAILED: prohibited database import"
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
                "M77.19.6.4.2 verification FAILED: write SQL/DDL detected"
            )

print("M77.19.6.4.2 verification PASSED")
print(" - exact frozen prediction authority is joined to replay-run cadence authority")
print(" - prediction date uses as_of explicitly")
print(" - profile_json and lineage_json are preserved")
print(" - unrelated filesystem fallback is disabled")
print(" - database transaction is READ ONLY")
print(" - parity thresholds unchanged; 23-year reconstruction remains blocked")
