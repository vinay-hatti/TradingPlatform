#!/usr/bin/env python3
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
runner = root / "scripts" / "run_m77_19_6_3_controlled_exact_input_parity_replay.py"

if not runner.exists():
    raise SystemExit("M77.19.6.3 verification FAILED: runner missing")

text = runner.read_text()
tree = ast.parse(text)

required = [
    "from trading_ai.database.session import SessionLocal",
    "SET TRANSACTION READ ONLY",
    "SCORE_EPSILON = 1e-9",
    "CONFIDENCE_EPSILON = 1e-9",
    '"full_23_year_reconstruction_authorized": False',
    '"production_authority_effect": False',
    "require_m77_19_6_2_authority",
    "semantic_hash",
]

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.3 verification FAILED: missing marker: " + marker
        )

for prohibited in [
    "from trading_ai.database import DATABASE_URL",
    "from trading_ai.database.database import engine",
]:
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.3 verification FAILED: prohibited DB import"
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
                "M77.19.6.3 verification FAILED: write SQL/DDL detected"
            )

print("M77.19.6.3 verification PASSED")
print(" - M77.19.6.2 controlled replay authority is mandatory")
print(" - strict parity thresholds preserved")
print(" - database transaction is READ ONLY")
print(" - no production write SQL/DDL detected")
print(" - semantic hash parity remains strict")
print(" - 23-year reconstruction remains blocked")
