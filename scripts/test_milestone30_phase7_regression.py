from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
TESTS=(
'scripts/test_realtime_position_mtm_foundation.py',
'scripts/test_realtime_portfolio_greeks_scenario_monitoring.py',
'scripts/test_dynamic_risk_limits_breach_alerts.py',
'scripts/test_continuous_monitoring_killswitch_reconciliation.py',
'scripts/test_position_risk_reporting_dashboard.py',
)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--allow-missing',action='store_true'); a=ap.parse_args(); missing=[]; failed=[]
    for script in TESTS:
        if not Path(script).exists(): missing.append(script); print('[MISSING]',script); continue
        print('[RUN]',script); r=subprocess.run([sys.executable,script]);
        if r.returncode: failed.append((script,r.returncode))
    if missing and not a.allow_missing: raise AssertionError('Missing Phase 7 tests: '+', '.join(missing))
    if failed: raise AssertionError('Failed Phase 7 tests: '+', '.join(f'{s}({c})' for s,c in failed))
    print('All available Milestone 30 Phase 7 regression assertions passed.')
if __name__=='__main__': main()
