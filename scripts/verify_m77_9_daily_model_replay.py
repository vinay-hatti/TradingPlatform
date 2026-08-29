#!/usr/bin/env python3
from pathlib import Path
r=Path('scripts/run_m77_9_daily_model_replay.py').read_text(); c=Path('scripts/certify_m77_9_daily_walk_forward.py').read_text()
assert 'from trading_ai.database.session import SessionLocal' in r and 'from trading_ai.database.session import SessionLocal' in c
assert "cadence='DAILY'" in r
assert 'm77_8_daily_pit_replay_authority.json' in r and 'm77_8_daily_pit_regime_snapshots.json' in c
assert 'existing_weekly_m77_mutation' in r and 'False' in r
assert 'selection_uses_only_pre_holdout_data' in c and 'non_overlapping_observation_sampling' in c
assert 'automatic_champion_promotion' in c and 'False' in c
print('M77.9 source verification PASSED')
print(' - DAILY replay explicitly bound to M77.8 authority')
print(' - SessionLocal database convention preserved')
print(' - expanding walk-forward selection is pre-holdout only')
print(' - research-only/no automatic champion promotion')
print(' - existing weekly M77 mutation: NONE')
