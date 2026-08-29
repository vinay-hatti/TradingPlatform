import argparse,subprocess,sys
from pathlib import Path
TESTS=('scripts/test_paper_trading_session_foundation.py','scripts/test_paper_scan_signal_decision_pipeline.py','scripts/test_paper_execution_fill_models.py','scripts/test_paper_position_lifecycle_pnl_exits.py','scripts/test_paper_automation_orchestration_recovery.py','scripts/test_paper_trading_operational_reporting.py')
def main():
 a=argparse.ArgumentParser();a.add_argument('--allow-missing',action='store_true');x=a.parse_args();miss=[];fail=[]
 for s in TESTS:
  if not Path(s).exists():miss.append(s);continue
  r=subprocess.run([sys.executable,s]);fail += [(s,r.returncode)] if r.returncode else []
 if miss and not x.allow_missing:raise AssertionError('Missing: '+','.join(miss))
 if fail:raise AssertionError(str(fail))
 print('All available Milestone 30 Phase 6 regression assertions passed.')
if __name__=='__main__':main()
