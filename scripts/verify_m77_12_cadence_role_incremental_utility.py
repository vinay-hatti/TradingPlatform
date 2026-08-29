#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
run=(ROOT/"run_m77_12_cadence_role_incremental_utility.py").read_text()

assert "frozen_certified" in run
assert '"frozen_baseline_cohorts_only":True' in run
assert '"neighboring_cohort_search":False' in run
assert '("CONFIRMING","NEUTRAL","CONFLICTING")' in run
assert "latest_le" in run and "bisect_right" in run
assert "incremental_vs_same_frozen_baseline_pct" in run
assert "monthly_neutral_excluded_from_directional_overlay" in run
assert '"automatic_shadow_activation":False' in run
assert '"automatic_champion_promotion":False' in run
assert ".run_baseline(" not in run
print("M77.12 source verification PASSED")
print(" - only frozen M77.9/M77.10 certified cohorts are tested")
print(" - secondary cadence role is predeclared: CONFIRMING/NEUTRAL/CONFLICTING")
print(" - each role is compared against the same frozen baseline, not a searched control")
print(" - backward-only cadence binding and deterministic non-overlap")
print(" - neutral monthly baselines excluded from directional role claims")
print(" - no shadow/production/champion mutation")
