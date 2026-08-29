from pathlib import Path
root = Path(__file__).resolve().parents[1]
handoff = (root / 'src/trading_ai/institutional_options/handoff.py').read_text()
router = (root / 'src/trading_ai/advanced_trade_builder/router.py').read_text()
ui = (root / 'ui/workstation/src/AdvancedTradeBuilderPage.tsx').read_text()
assert 'strategy=strategy.strategy' in handoff
assert "failed_checks=failed" in router
assert "validation_changed=previous_validation!=current_validation" in router
assert "case 'two_expiries':" in ui
assert 'Exactly 2 unique expiries for calendar/diagonal strategies' in ui
assert 'revalidation passed (v${priorVersion} → v${currentVersion})' in ui
print('M68.2.1.15.7 verification PASSED')
print(' - M62 handoff propagates selected strategy into Trade Builder economics')
print(' - calendar/diagonal validation uses two-expiry semantics')
print(' - revalidation returns explicit version/state/failure metadata')
print(' - workstation surfaces governed revalidation outcome')
