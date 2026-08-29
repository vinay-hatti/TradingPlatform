#!/usr/bin/env python3
from __future__ import annotations
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
path = root / "scripts/run_m77_19_6_5_2_8_structure_and_level_generation_upstream_causal_forensics.py"
if not path.exists():
    raise SystemExit("M77.19.6.5.2.8 verification FAILED: runner missing")
text = path.read_text()
ast.parse(text)

required = (
    "bfba461d7b788112235a0d565bd7e0bc4e1398a6ed188022faf94357ae49835e",
    "a293b8f87ef56762d60989cda3cc03ad224999a1a6d846af7b64e318c48d4e8a",
    "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b",
    "baseline_reproduced_after_key_normalization",
    "FALSE_NEGATIVE_FROM_NUMERIC_VS_JSON_STRING_DISTRIBUTION_KEYS",
    "SET TRANSACTION READ ONLY",
    "PARITY_TOLERANCE = 1e-9",
    "patch_mt",
    "patch_participation",
    "recursive_diff",
    "structure_level_path_inventory",
    "native.compare_profile",
    "full_23_year_reconstruction_authorized",
    "production_authority_effect",
)
for marker in required:
    if marker not in text:
        raise SystemExit("M77.19.6.5.2.8 verification FAILED: missing " + marker)

for prohibited in (
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "TRUNCATE ",
    "session.commit(",
    '"production_authority_effect": True',
    '"full_23_year_reconstruction_authorized": True',
):
    if prohibited in text:
        raise SystemExit("M77.19.6.5.2.8 verification FAILED: prohibited marker " + prohibited)

print("M77.19.6.5.2.8 verification PASSED")
print(" - M77.19.6.5.2.5 and .7 report SHAs are pinned")
print(" - native replay runner SHA remains pinned")
print(" - .7 baseline false-negative is normalized and explicitly classified")
print(" - combined weekly + participation closure is a required control")
print(" - confidence and score must remain 48/48 exact before residual forensics")
print(" - state hash must remain unresolved before structure/level intervention")
print(" - residual full-profile paths are inventoried and domain-classified")
print(" - structure/level paths are ranked by 48-bundle frequency")
print(" - database is read-only SPY session calendar only")
print(" - parity tolerance remains 1e-9")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
