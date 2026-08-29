from pathlib import Path
root = Path(__file__).resolve().parents[1]
handoff = (root/'src/trading_ai/institutional_options/handoff.py').read_text()
execsvc = (root/'src/trading_ai/execution_intelligence/service.py').read_text()
trade = (root/'src/trading_ai/advanced_trade_builder/service.py').read_text()
assert 'AdvancedTradeBuilderService.economics(tuple(legs), float(capital), float(risk_budget_pct), strategy.strategy)' in handoff
assert 'AdvancedTradeBuilderService.economics(trade_legs,float(tp.capital),float(tp.risk_budget_pct),tp.strategy)' in execsvc
assert "TIME_SPREAD_STRATEGIES={'CALL_DIAGONAL','PUT_DIAGONAL','CALL_CALENDAR','PUT_CALENDAR'" in trade
print('M74.4.1 strategy propagation verification: PASSED')
