from pathlib import Path
root=Path(__file__).resolve().parents[1]
svc=(root/'src/trading_ai/advanced_trade_builder/service.py').read_text()
ui=(root/'ui/workstation/src/AdvancedTradeBuilderPage.tsx').read_text()
assert 'TIME_SPREAD_STRATEGIES' in svc
assert "'CALL_DIAGONAL'" in svc and "'PUT_DIAGONAL'" in svc
assert "'CALL_CALENDAR'" in svc and "'PUT_CALENDAR'" in svc
assert "return {'two_expiries':len(expiries)==2}" in svc
assert "return {'single_expiry':len(expiries)==1}" in svc
assert 'normalized_strategy not in cls.TIME_SPREAD_STRATEGIES' in svc
assert "case 'two_expiries':" in ui
assert 'Exactly 2 unique expiries for calendar/diagonal strategies' in ui
print('M74.4.0 strategy-aware Trade Builder validation verification: PASSED')
