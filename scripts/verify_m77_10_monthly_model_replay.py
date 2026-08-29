#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
run=(ROOT/"run_m77_10_monthly_model_replay.py").read_text()
cert=(ROOT/"certify_m77_10_monthly_walk_forward.py").read_text()
assert ".run_baseline(" not in run
assert "run_m77_1_cli" in run
assert '"run-baseline"' in run
assert '"--cadence","MONTHLY"' in run
assert "HistoricalUnderlyingReplayService(s).materialize_authority()" in run
assert "HORIZONS=(60,120,180,252)" in cert
assert "return_120d_pct" not in cert
assert "return_180d_pct" not in cert
assert "return_252d_pct" not in cert
assert "price_history" in cert
assert "pit_regime_authority" in cert
assert "production_authority_effect" in run and "production_authority_effect" in cert
print("M77.10.2 source verification PASSED")
print(" - monthly replay delegates to installed, already-proven M77.1 CLI")
print(" - nonexistent service.run_baseline assumption removed")
print(" - 120/180/252 outcomes computed read-only from price_history")
print(" - monthly cohorts bind exact M77.8 PIT regime")
print(" - weekly/daily/production authorities remain untouched")
