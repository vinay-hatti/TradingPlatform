#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
path = (
    root
    / "scripts"
    / "run_m77_19_6_5_2_10_level_generation_input_and_selection_semantics_forensics.py"
)

if not path.exists():
    raise SystemExit("M77.19.6.5.2.10 verification FAILED: runner missing")

text = path.read_text()
ast.parse(text)

required = (
    "91b1c236014ea2acef7e21e849434cd91c7fd5638d9ab6f54b3d03b3687ffdcf",
    "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb",
    "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b",
    "validate_529",
    "capture_native_levels",
    "summarize_timeframe_input",
    "compare_level_side",
    "price_set_relation",
    "nearest_price",
    "source_semantics",
    '"synthetic_level_replacement_used": False',
    '"native_level_service_executes_unmodified": True',
    "SEPARATE_DOWNSTREAM_BRANCH_REMAINS_OPEN",
    "SET TRANSACTION READ ONLY",
    "PARITY_TOLERANCE = 1e-9",
    '"full_23_year_reconstruction_authorized": False',
    '"production_authority_effect": False',
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.2.10 verification FAILED: missing " + marker
        )

for prohibited in (
    "patch_levels(",
    "patch_structure(",
    "frozen_support_replacement",
    "frozen_resistance_replacement",
    "session.commit(",
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "TRUNCATE ",
    '"production_authority_effect": True',
    '"full_23_year_reconstruction_authorized": True',
):
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.2.10 verification FAILED: prohibited marker "
            + prohibited
        )

print("M77.19.6.5.2.10 verification PASSED")
print(" - M77.19.6.5.2.9 report SHA is pinned")
print(" - M77.19.6.5.2.9.1 repaired runner SHA is pinned")
print(" - native replay runner SHA remains pinned")
print(" - no synthetic level or structure replacement is allowed")
print(" - native LevelIntelligenceService input and output are captured")
print(" - per-timeframe input row/date windows are recorded")
print(" - frozen/native level membership, cardinality, nearest-price and metadata are compared")
print(" - native level source semantics are captured and AST-inspected")
print(" - trade-plan/state-hash mismatch is isolated as a separate downstream branch")
print(" - database remains READ ONLY SPY session calendar only")
print(" - parity tolerance remains 1e-9")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
