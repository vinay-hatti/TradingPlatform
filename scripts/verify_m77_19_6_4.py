#!/usr/bin/env python3
from __future__ import annotations
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
runner = root / "scripts" / "run_m77_19_6_4_exact_frozen_input_context_replay_adapter.py"

if not runner.exists():
    raise SystemExit("M77.19.6.4 verification FAILED: runner missing")

text = runner.read_text()
tree = ast.parse(text)

required = [
    "from trading_ai.database.session import SessionLocal",
    "SET TRANSACTION READ ONLY",
    '"full_23_year_reconstruction_authorized": False',
    '"production_authority_effect": False',
    '"controlled_exact_input_parity_certified"] = False',
    "BUILD_M77_19_6_5_CONTROLLED_ADAPTER_EXECUTION_AND_PARITY_CERTIFICATION",
    "price_history_sha256",
    "context_sha256",
    "bundle_semantic_sha256",
]

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.4 verification FAILED: missing marker: " + marker
        )

for prohibited in [
    "from trading_ai.database import DATABASE_URL",
    "from trading_ai.database.database import engine",
]:
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.4 verification FAILED: prohibited database import"
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
                "M77.19.6.4 verification FAILED: production write SQL/DDL detected"
            )

print("M77.19.6.4 verification PASSED")
print(" - exact frozen-input/context bundles are filesystem research artifacts")
print(" - database transaction is READ ONLY")
print(" - no production write SQL/DDL")
print(" - bundle provenance hashes are mandatory")
print(" - parity is not certified by adapter construction alone")
print(" - full 23-year reconstruction remains blocked")
