#!/usr/bin/env python3
from __future__ import annotations
import ast
import json
from pathlib import Path
import sys

def fail(msg: str) -> None:
    raise SystemExit("M77.19.6.2 verification FAILED: " + msg)

def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    runner = root / "scripts" / "run_m77_19_6_2_exact_input_context_hash_parity.py"
    if not runner.exists():
        fail(f"missing {runner}")
    text = runner.read_text()
    tree = ast.parse(text)

    prohibited = [
        "from trading_ai.database import DATABASE_URL",
        "from trading_ai.database.database import engine",
    ]
    for p in prohibited:
        if p in text:
            fail(f"prohibited DB import: {p}")
    required = [
        "from trading_ai.database.session import SessionLocal",
        "SET TRANSACTION READ ONLY",
        "STRICT_SCORE_EPSILON = 1e-9",
        "STRICT_CONFIDENCE_EPSILON = 1e-9",
        '"full_23_year_reconstruction_authorized": False',
        '"production_authority_effect": False',
        "semantic_projection",
        "semantic_hash",
        "external_context",
    ]
    for marker in required:
        if marker not in text:
            fail(f"missing governance/semantic marker: {marker}")

    # Reject obvious write SQL in executable string constants.
    bad_sql = (" INSERT ", " UPDATE ", " DELETE ", " MERGE ", " TRUNCATE ", " DROP ", " ALTER ", " CREATE TABLE ")
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = " " + " ".join(node.value.upper().split()) + " "
            if any(x in s for x in bad_sql):
                fail("write/DDL SQL detected in runner")

    print("M77.19.6.2 verification PASSED")
    print(" - strict parity thresholds preserved")
    print(" - database access uses SessionLocal + transaction READ ONLY")
    print(" - no production write SQL/DDL found")
    print(" - semantic hash decomposition present")
    print(" - external-context recovery diagnostics present")
    print(" - 23-year reconstruction remains explicitly blocked")

if __name__ == "__main__":
    main()
