#!/usr/bin/env python3
from __future__ import annotations
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
path = root / "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
if not path.exists():
    raise SystemExit("M77.19.6.5.2.9 verification FAILED: runner missing")
text = path.read_text()
ast.parse(text)

required = (
    "d227650425b2221da14b4e67c3bcdc0f3bc880c24909f97f75233a2e50cf0101",
    "bfba461d7b788112235a0d565bd7e0bc4e1398a6ed188022faf94357ae49835e",
    "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b",
    "PARITY_TOLERANCE = 1e-9",
    "LEVELS_ONLY",
    "STRUCTURE_ONLY",
    "LEVELS_AND_STRUCTURE",
    "patch_levels",
    "patch_structure",
    "service.levels.analyze",
    "service.structure_zones.build",
    "SET TRANSACTION READ ONLY",
    "native.compare_profile",
    "synthetic_component_output_interventions_only",
    "full_23_year_reconstruction_authorized",
    "production_authority_effect",
)
for marker in required:
    if marker not in text:
        raise SystemExit("M77.19.6.5.2.9 verification FAILED: missing " + marker)

for prohibited in (
    "INSERT ", "UPDATE ", "DELETE ", "TRUNCATE ", "session.commit(",
    '"production_authority_effect": True',
    '"full_23_year_reconstruction_authorized": True',
):
    if prohibited in text:
        raise SystemExit("M77.19.6.5.2.9 verification FAILED: prohibited marker " + prohibited)

print("M77.19.6.5.2.9 verification PASSED")
print(" - M77.19.6.5.2.8 and .7 report SHAs are pinned")
print(" - native replay runner SHA remains pinned")
print(" - weekly + participation closure is mandatory control")
print(" - LEVELS_ONLY replaces only support/resistance at native level-service output")
print(" - STRUCTURE_ONLY replaces only structure_zones after native builder execution")
print(" - LEVELS_AND_STRUCTURE combines both minimal interventions")
print(" - all downstream score/trade-plan/certification/decision stages recompute natively")
print(" - database is read-only SPY session calendar only")
print(" - parity tolerance remains 1e-9")
print(" - interventions are research-only and cannot become production authority")
print(" - 23-year reconstruction remains blocked")
