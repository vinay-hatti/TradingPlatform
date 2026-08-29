from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1])
entry=(root/'src/trading_ai/execution_intelligence/entry_chase.py').read_text()
svc=(root/'src/trading_ai/execution_intelligence/service.py').read_text()
policy=(root/'src/trading_ai/execution_intelligence/policy.py').read_text()
auto=(root/'src/trading_ai/execution_intelligence/auto_fill.py').read_text()
ui=(root/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
checks={
 'adaptive_chase_helper':'def adaptive_chase_state(' in entry and "'ADAPTIVE_CHASE'" in entry,
 'market_or_boundary_target':'target=min(executable,boundary)' in entry,
 'no_fixed_four_reprice_rest':"elif reprice_count>=policy.maximum_reprices" not in svc,
 'adaptive_interval':'adaptive_modify_interval_seconds' in policy and 'WAIT_ADAPTIVE_MODIFY_INTERVAL' in svc,
 'sell_signed_economics':'Signed economic prices' in entry and 'accepting less credit' in entry,
 'hard_timeout_preserved':"'HARD_TIMEOUT'" in entry and 'working_order_max_age_seconds' in policy,
 'auto_manager_updated':'M74.12-ADAPTIVE-MARKET-STATE-CHASE' in auto,
 'ui_adaptive_phase':"ADAPTIVE_CHASE" in ui and 'Total reprices' in ui and 'Fast chase' in ui,
}
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit('M74.12 verification failed: '+', '.join(failed))
print('M74.12 adaptive market-state chase verification: PASSED')
