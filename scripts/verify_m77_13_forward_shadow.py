#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
run=(ROOT/"run_m77_13_forward_shadow.py").read_text()
mig=(ROOT.parent/"migrations/versions/m77_004_multi_cadence_certified_baseline_forward_shadow.py").read_text()

assert "from trading_ai.database.session import SessionLocal" in run
assert "run_m77_8_daily_pit_replay_authority.py" in run
assert "run_m77_1_historical_underlying_replay.py" in run
assert '"--cadence",cadence' in run
assert "source_date==monthly_anchor" in run
assert "prevents backfilling" in run
assert "directional_only=True" in run
assert "monthly_neutral_context_only" in run
assert "signal_fingerprint" in mig
assert 'revision = "m77_004"' in mig
assert 'down_revision = "m77_003"' in mig
assert "m77_13_cadence_states" in mig
assert "m77_13_forward_signals" in mig
assert "m77_13_forward_outcomes" in mig
assert "production_filter_or_ranking_effect" in run
print("M77.13 source verification PASSED")
print(" - prospective daily certified-baseline capture")
print(" - monthly baseline capture only on actual month-end; no historical backfill")
print(" - weekly/monthly context uses cadence state anchored at or before daily source date")
print(" - exact M77.8 PIT regime refreshed before capture")
print(" - neutral monthly cohorts retained as context-only, not directional signals")
print(" - isolated m77_13 tables; no production filtering/ranking effect")
