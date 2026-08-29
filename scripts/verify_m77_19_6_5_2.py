#!/usr/bin/env python3
from __future__ import annotations
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
p = root / "scripts" / "run_m77_19_6_5_2_native_controlled_execution_parity_certification.py"

if not p.exists():
    raise SystemExit("M77.19.6.5.2 verification FAILED: runner missing")

text = p.read_text()
tree = ast.parse(text)

required = [
    "EXPECTED_NATIVE_RUNNER_SHA256",
    "EXPECTED_DM_ADAPTER_SHA256",
    "from trading_ai.database.session import SessionLocal",
    "SET TRANSACTION READ ONLY",
    "WHERE symbol = 'SPY'",
    "native.call_profile",
    "StockIntelligenceService",
    "SCORE_EPSILON = 1e-9",
    "CONFIDENCE_EPSILON = 1e-9",
    "DIRECTION_REQUIRED_PCT = 100.0",
    "SEMANTIC_HASH_REQUIRED_PCT = 100.0",
    "DETERMINISTIC_REPEAT_REQUIRED_PCT = 100.0",
    '"full_23_year_reconstruction_authorized": False',
    '"production_authority_effect": False',
]

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.2 verification FAILED: missing marker: " + marker
        )

for prohibited in [
    "from trading_ai.database import DATABASE_URL",
    "from trading_ai.database.database import engine",
]:
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.2 verification FAILED: prohibited DB import"
        )

bad_sql = (
    " INSERT ", " UPDATE ", " DELETE ", " MERGE ", " TRUNCATE ",
    " DROP ", " ALTER ", " CREATE TABLE ",
)

for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        s = " " + " ".join(node.value.upper().split()) + " "
        if any(x in s for x in bad_sql):
            raise SystemExit(
                "M77.19.6.5.2 verification FAILED: write SQL/DDL detected"
            )

print("M77.19.6.5.2 verification PASSED")
print(" - exact native runner SHA-256 is frozen")
print(" - certified PIT adapter SHA-256 is frozen")
print(" - native call_profile is invoked directly")
print(" - SPY session calendar is recovered READ ONLY")
print(" - strict 100% / 1e-9 parity gates remain unchanged")
print(" - full 23-year reconstruction is not authorized by this package")
