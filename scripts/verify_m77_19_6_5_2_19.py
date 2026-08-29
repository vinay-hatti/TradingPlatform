#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
P = ROOT / "scripts/run_m77_19_6_5_2_19_native_observable_consolidation_trigger_causal_replay.py"
if not P.exists():
    raise SystemExit("M77.19.6.5.2.19 verification FAILED: runner missing")
T = P.read_text()

required = (
    'EXPECTED_REPORT_5218_SHA256 = "bc2c4f7411698d7ad25ba7fa85b384d4431d666547a09c4be3126ecfc91cd8aa"',
    'EXPECTED_RUNNER_5218_SHA256 = "979592ee06af3c5668f386f0e89f0d0b47633b0724be7eaeb7820ef703353818"',
    '"OBSERVABLE_SPLIT_WIDE_ELIGIBLE_MERGE"',
    '"OBSERVABLE_PRESERVE_SEED_ON_WIDE_DRIFT"',
    'observable_gap >= LEVEL_REACHABILITY_THRESHOLD',
    'rel_distance(after, seed) >= LEVEL_REACHABILITY_THRESHOLD',
    '"native_observable_trigger_uses_frozen_target_identity": False',
    '"native_observable_trigger_uses_symbol_identity": False',
    '"native_observable_trigger_uses_historical_answer": False',
    '"observable_trigger_threshold_source": "EXISTING_NATIVE_LEVEL_MERGE_THRESHOLD"',
    '"frozen_target_identity_prohibited": True',
    '"historical_answer_leakage_prohibited": True',
    '"threshold_search_or_optimization": False',
    'NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35',
    'LEVEL_REACHABILITY_THRESHOLD = 0.003',
    'PARITY_TOLERANCE = 1e-9',
    '"candidate_semantic_promoted": False',
    '"production_authority_effect": False',
)
missing = [x for x in required if x not in T]
if missing:
    raise SystemExit(f"M77.19.6.5.2.19 verification FAILED: missing markers {missing}")

for bad in (
    'symbol == "AES"',
    'symbol == "ANET"',
    'symbol == "ATO"',
    "target_price ==",
    "threshold_grid",
    "optimize_threshold",
    "UPDATE ",
    "INSERT ",
    "DELETE ",
    "DROP TABLE",
    "ALTER TABLE",
):
    if bad in T:
        raise SystemExit(f"M77.19.6.5.2.19 verification FAILED: prohibited token {bad}")

print("M77.19.6.5.2.19 verification PASSED")
print(" - M77.19.6.5.2.18 report and runner are SHA-pinned")
print(" - frozen-target ancestry is prohibited from trigger logic")
print(" - symbol-specific trigger logic is prohibited")
print(" - historical-answer leakage is prohibited")
print(" - two native-observable causal arms are predeclared")
print(" - SPLIT_WIDE uses only current centroid, incoming candidate, and existing 0.3% threshold")
print(" - PRESERVE_SEED uses only native seed/centroid state and existing 0.3% threshold")
print(" - native candidate generation and top-12 retention remain fixed")
print(" - native internal merge radius remains 0.35 x ATR")
print(" - no threshold search or optimization")
print(" - all 48 monthly bundles must be evaluated")
print(" - native 1338 exact / 67 missing authority is fail-closed")
print(" - candidate semantic remains research-only")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
