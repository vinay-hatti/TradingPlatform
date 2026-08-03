from pathlib import Path
import sys
root=Path(sys.argv[1])
app=(root/'ui/workstation/src/App.tsx').read_text()
chrome=(root/'ui/workstation/src/WorkspaceChrome.tsx').read_text()
pages=(root/'ui/workstation/src/pages.tsx').read_text()
router=(root/'src/trading_ai/production_api/router.py').read_text()
assert "value === 'risk' || value === 'positions' || value === 'exits'" in app
assert "'risk', 'positions', 'exits'" not in chrome
assert "['risk', 'Risk'" not in pages
assert "['positions', 'Positions'" not in pages
assert "['exits', 'Exits'" not in pages
assert 'm37/execution_risk_control.json' not in router
assert 'm39/position_assessments.json' not in router
assert 'm39/exit_instructions.json' not in router
assert 'canonical_portfolio_intelligence' in router
assert 'canonical_managed_positions' in router
assert 'canonical_position_decisions' in router
print('Legacy Risk/Positions/Exits cleanup assertions passed.')
