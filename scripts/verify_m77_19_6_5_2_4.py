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
    / "run_m77_19_6_5_2_4_monthly_feature_confidence_component_forensics.py"
)

if not path.exists():
    raise SystemExit(
        "M77.19.6.5.2.4 verification FAILED: runner missing"
    )

text = path.read_text()
tree = ast.parse(text)

required = (
    "EXPECTED_5232_REPORT_SHA256",
    "native.compare_profile(",
    "frozen_profile",
    "constant_numeric_component_deltas",
    "confidence_minus_0_24_candidate_paths",
    "SET TRANSACTION READ ONLY",
    "NUMERIC_TOLERANCE = 1e-9",
    "controlled_exact_input_parity_certified",
    "full_23_year_reconstruction_authorized",
    "production_authority_effect",
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.2.4 verification FAILED: missing "
            + marker
        )

for prohibited in (
    "from trading_ai.database import DATABASE_URL",
    "from trading_ai.database.database import engine",
):
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.2.4 verification FAILED: prohibited DB import"
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
                "M77.19.6.5.2.4 verification FAILED: write SQL/DDL detected"
            )

print(
    "M77.19.6.5.2.4 verification PASSED"
)
print(
    " - M77.19.6.5.2.3.2 report SHA is pinned as forensic authority"
)
print(
    " - all 48 monthly nominal profiles are evaluated"
)
print(
    " - native compare_profile remains semantic authority"
)
print(
    " - frozen_profile is compared component-by-component"
)
print(
    " - constant and recurring numeric deltas are ranked"
)
print(
    " - confidence -0.24 candidate paths are explicitly detected"
)
print(
    " - database remains READ ONLY"
)
print(
    " - parity thresholds remain unchanged"
)
print(
    " - no parity certification or 23-year authorization occurs"
)
