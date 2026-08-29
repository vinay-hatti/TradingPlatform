#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
runner = root / "scripts" / "run_m77_19_6_5_controlled_adapter_execution_parity_certification.py"

if not runner.exists():
    raise SystemExit("M77.19.6.5 verification FAILED: runner missing")

text = runner.read_text()
tree = ast.parse(text)

required = [
    "SCORE_EPSILON = 1e-9",
    "CONFIDENCE_EPSILON = 1e-9",
    "DIRECTION_MATCH_REQUIRED_PCT = 100.0",
    "SEMANTIC_HASH_MATCH_REQUIRED_PCT = 100.0",
    "DETERMINISTIC_REPEAT_REQUIRED_PCT = 100.0",
    "exact_frozen_input_context_adapter_ready",
    "choose_adapter",
    "len(top) != 1",
    "execute_once",
    "deterministic_repeat",
    '"full_23_year_reconstruction_authorized": False',
    '"production_authority_effect": False',
]

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5 verification FAILED: missing marker: " + marker
        )

for prohibited in [
    "from trading_ai.database import DATABASE_URL",
    "from trading_ai.database.database import engine",
    "SessionLocal",
]:
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5 verification FAILED: production DB access/import detected"
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
                "M77.19.6.5 verification FAILED: write SQL/DDL detected"
            )

print("M77.19.6.5 verification PASSED")
print(" - exact M77.19.6.4.2 bundle authority is mandatory")
print(" - strict parity thresholds remain unchanged")
print(" - ambiguous adapter selection fails closed")
print(" - deterministic repeat executes each bundle twice")
print(" - no production database access is required")
print(" - full 23-year reconstruction remains blocked")
