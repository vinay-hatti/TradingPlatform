from pathlib import Path
REQ=('paper_trading_policy.py','paper_scan_policy.py','paper_execution_policy.py','paper_position_policy.py','paper_automation_orchestrator.py','paper_trading_reporting.py')
CMDS=('paper-trading-session-test','paper-scan-pipeline-test','paper-execution-test','paper-position-test','paper-automation-recovery-test','paper-trading-report','milestone30-phase6-regression-test','milestone30-phase6-closure-test')
def main():
 for n in REQ:assert Path('src/trading_ai/paper_trading/'+n).exists(),n
 s=Path('src/trading_ai/__main__.py').read_text()
 for c in CMDS:assert c in s,c
 print('All Milestone 30 Phase 6 closure assertions passed.')
if __name__=='__main__':main()
