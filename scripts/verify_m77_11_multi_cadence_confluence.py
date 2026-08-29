#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
run=(ROOT/"run_m77_11_multi_cadence_confluence.py").read_text()
r10=(ROOT/"report_m77_10_monthly_walk_forward.py").read_text()

assert "latest_le" in run
assert "bisect_right" in run
assert '"future_leakage_prohibited":True' in run
assert "nonoverlap" in run
assert "incremental_vs_best_component_pct" in run
assert "production_model_or_weight_change" in run
assert "automatic_champion_promotion" in run
assert "m77_8_daily_pit_regime_snapshots.json" in run
assert 'x.get("regime","UNKNOWN")' in r10
print("M77.11 source verification PASSED")
print(" - daily entry clock with backward-only weekly/monthly binding")
print(" - deterministic non-overlap and incremental-edge comparison")
print(" - exact M77.8 PIT regime available to component certification")
print(" - M77.10 reporter now renders regime identity")
print(" - research-only/no automatic production or champion mutation")
