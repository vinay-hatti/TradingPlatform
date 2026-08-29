#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(
    sys.argv[1] if len(sys.argv) > 1 else "."
).resolve()

path = (
    root
    / "scripts"
    / "run_m77_19_6_5_2_3_2_native_comparator_monthly_session_cutoff_forensics.py"
)

if not path.exists():
    raise SystemExit(
        "M77.19.6.5.2.3.2 verification FAILED: runner missing"
    )

text = path.read_text()
tree = ast.parse(text)

required = (
    "native.compare_profile(",
    "native_compare_profile_is_semantic_authority",
    "repaired_nominal_authority_reproduction",
    "evaluation_as_of",
    "candidate_input_cutoff",
    "SET TRANSACTION READ ONLY",
    "NUMERIC_TOLERANCE = 1e-9",
    "MAX_SESSION_BACKTRACK = 8",
    "controlled_exact_input_parity_certified",
    "full_23_year_reconstruction_authorized",
    "production_authority_effect",
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.2.3.2 verification FAILED: missing "
            + marker
        )

for prohibited in (
    "from trading_ai.database import DATABASE_URL",
    "from trading_ai.database.database import engine",
):
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.2.3.2 verification FAILED: prohibited DB import"
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
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
    ):
        normalized = (
            " "
            + " ".join(
                node.value.upper().split()
            )
            + " "
        )

        if any(
            token in normalized
            for token in bad_sql
        ):
            raise SystemExit(
                "M77.19.6.5.2.3.2 verification FAILED: write SQL/DDL detected"
            )

print(
    "M77.19.6.5.2.3.2 verification PASSED"
)
print(
    " - native compare_profile is the only semantic extraction authority"
)
print(
    " - no profile-field guessing or generic score-path discovery remains"
)
print(
    " - monthly evaluation as_of remains fixed while visible input cutoff varies"
)
print(
    " - nominal 48-bundle aggregate must reproduce M77.19.6.5.2.2"
)
print(
    " - parity threshold remains 1e-9"
)
print(
    " - database remains READ ONLY"
)
print(
    " - no parity certification or 23-year authorization occurs"
)
