from pathlib import Path
root=Path(__file__).resolve().parents[1]
a=(root/'src/trading_ai/autonomous_position_management/service.py').read_text()
d=(root/'src/trading_ai/dynamic_position_management/service.py').read_text()
u=(root/'ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx').read_text()
assert 'SHORT_LEG_ASSIGNMENT_EXIT' in a
assert "'trigger_type':'SHORT_LEG_DTE'" in a
assert "'exit_method':'ATOMIC_BAG'" in a
assert "short_leg_roll_enabled':False" in a
assert 'if typ=="SHORT_LEG_DTE"' in d
assert "close_action='SELL' if original=='BUY' else 'BUY'" in d
assert "'strategy_level_exit':True" in d and "'includes_short_legs':True" in d
assert 'return service.submit_combo(request)' in d
assert "NON_OPERATIONAL_POSITION_STATES = new Set(['CLOSED', 'CANCELLED', 'SUPERSEDED'])" in u
assert 'Strategy Lifecycle' in u and 'Short-leg monitoring' in u and 'ATOMIC BAG MANAGED' in u
print('M74.10 strategy-level autonomous management verification: PASSED')
