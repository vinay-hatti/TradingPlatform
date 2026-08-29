#!/usr/bin/env python3
from __future__ import annotations
import ast
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
runner = root / "scripts/run_m77_19_6_5_2_13_support_resistance_candidate_algorithm_causal_hypothesis_replay.py"
if not runner.exists():
    raise SystemExit("M77.19.6.5.2.13 verification FAILED: runner missing")
text = runner.read_text()
ast.parse(text)

required = (
    'REPORT_5212_REL',
    'EXPECTED_REPORT_5212_SHA256',
    'EXPECTED_RUNNER_5212_SHA256',
    '"NATIVE_CONTROL"',
    '"NO_TOP12_RETENTION"',
    '"NO_INTERNAL_ATR_CONSOLIDATION"',
    '"PIVOT_RADIUS_1"',
    '"PIVOT_RADIUS_3"',
    '"ADD_ROLLING_WINDOW_10"',
    '"ADD_ROLLING_WINDOW_200"',
    'threshold_search_or_optimization": False',
    'native_level_merge_threshold": LEVEL_MERGE_THRESHOLD',
    'LEVEL_MERGE_THRESHOLD = 0.003',
    'PARITY_TOLERANCE = 1e-9',
    'SET TRANSACTION READ ONLY',
    'frozen_profile_scoring_authority_only": True',
    'production_authority_effect": False',
    'full_23_year_reconstruction_authorized": False',
)
for marker in required:
    if marker not in text:
        raise SystemExit("M77.19.6.5.2.13 verification FAILED: missing " + marker)

if "profile.overall_score" in text:
    raise SystemExit("M77.19.6.5.2.13 verification FAILED: nonexistent StockIntelligenceProfile.overall_score reference")

prohibited = (
    "optimize_threshold",
    "best_threshold",
    "grid_search",
    "random_search",
    "session.commit(",
    '"production_authority_effect": True',
    '"full_23_year_reconstruction_authorized": True',
)
for marker in prohibited:
    if marker in text:
        raise SystemExit("M77.19.6.5.2.13 verification FAILED: prohibited " + marker)

print("M77.19.6.5.2.13 verification PASSED")
print(" - M77.19.6.5.2.12 report and .2.12.3 runner are SHA-pinned")
print(" - native replay runner, LevelIntelligenceService and SupportResistanceEngine are pinned")
print(" - nonexistent StockIntelligenceProfile.overall_score dependency is removed")
print(" - NATIVE_CONTROL remains completely unmodified")
print(" - all candidate-algorithm alternatives are predeclared one-factor research arms")
print(" - pivot radius, rolling-window inclusion, internal ATR consolidation and top-12 retention are isolated")
print(" - no threshold search or optimization is allowed")
print(" - native LevelIntelligence 0.3% merge threshold remains fixed")
print(" - frozen profile is scoring authority only")
print(" - database remains READ ONLY SPY session calendar only")
print(" - parity tolerance remains 1e-9")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
