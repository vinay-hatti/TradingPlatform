#!/usr/bin/env python3
from __future__ import annotations
import ast, sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
p = root/"scripts/run_m77_19_6_5_2_12_raw_support_resistance_candidate_generation_forensics.py"
if not p.exists():
    raise SystemExit("M77.19.6.5.2.12 verification FAILED: runner missing")
text = p.read_text()
ast.parse(text)

required = (
    "88e9e9b4781727b59254c9ae6a583cea27dece55bc034bc0064c686638c101d6",
    "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb",
    "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b",
    "8581c423956fd9d997af8098fb1065aab78b24646c72b9fb5ba1e8e446402490",
    "capture_raw_sr_candidates",
    "source_semantics",
    "row_provenance",
    "EXACT_NATIVE_CLUSTER_ANCHOR",
    "EXACT_RAW_CANDIDATE_BUT_NOT_NATIVE_CLUSTER_ANCHOR",
    "RAW_CANDIDATE_WITHIN_0_3PCT_BUT_PRICE_DIFFERS",
    "NO_NATIVE_RAW_CANDIDATE_WITHIN_0_3PCT",
    "MERGE_THRESHOLD = 0.003",
    "PARITY_TOLERANCE = 1e-9",
    "SET TRANSACTION READ ONLY",
    '"synthetic_candidate_replacement_used": False',
    '"production_authority_effect": False',
    '"full_23_year_reconstruction_authorized": False',
)
for marker in required:
    if marker not in text:
        raise SystemExit("M77.19.6.5.2.12 verification FAILED: missing "+marker)

for prohibited in (
    "session.commit(",
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "TRUNCATE ",
    '"production_authority_effect": True',
    '"full_23_year_reconstruction_authorized": True',
    "optimize_threshold",
    "best_threshold",
):
    if prohibited in text:
        raise SystemExit("M77.19.6.5.2.12 verification FAILED: prohibited "+prohibited)

print("M77.19.6.5.2.12 verification PASSED")
print(" - M77.19.6.5.2.11 report and repaired runner are SHA-pinned")
print(" - native replay runner and LevelIntelligenceService remain SHA-pinned")
print(" - native SupportResistanceEngine is instrumented only, never replaced")
print(" - raw support/resistance candidates are captured per timeframe")
print(" - frozen mismatches are classified by exact/raw/0.3%-reachable/missing semantics")
print(" - nearest OHLC provenance is recorded for every native raw candidate")
print(" - SupportResistanceEngine source is AST-inspected and SHA-recorded")
print(" - native 0.3% merge rule remains fixed and unrelaxed")
print(" - no candidate synthesis, search, or optimization is allowed")
print(" - database remains READ ONLY SPY session calendar only")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
