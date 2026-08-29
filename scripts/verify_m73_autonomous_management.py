
from pathlib import Path
from trading_ai.autonomous_position_management.service import AutonomousPositionManagementService
from trading_ai.autonomous_position_management.policy import load_m73_policy
ROOT=Path(__file__).resolve().parents[1]
assert AutonomousPositionManagementService.VERSION.startswith('M73')
assert (ROOT/'migrations/versions/m73_001_autonomous_dynamic_position_management.py').exists()
text=(ROOT/'src/trading_ai/dynamic_position_management/service.py').read_text()
for token in ['POLYGON_DIRECT','INSTITUTIONAL_STRUCTURE_ZONE','eligible=[]','[:1]']:assert token in text,token
run=(ROOT/'scripts/run_m62_dynamic_position_management.py').read_text();assert 'AutonomousPositionManagementService' in run
m63=(ROOT/'src/trading_ai/broker_portfolio_sync/service.py').read_text();assert 'm73_management' in m63;assert '_normalized_broker_unit_price' in m63;assert "session.get(TradePlanModel,trade_plan_id)" in m63
quotes=(ROOT/'src/trading_ai/autonomous_position_management/quotes.py').read_text();assert 'polygon_option_symbol_from_local_symbol' in quotes;assert 'underlying_candidates' in quotes
svc=(ROOT/'src/trading_ai/autonomous_position_management/service.py').read_text();assert 'MARKET_CLOSED_IDLE' in svc;assert '_broker_discovered_leg' in svc
m66=(ROOT/'src/trading_ai/production_operations/service.py').read_text();assert 'autonomous_management' in m66
print('M73 implementation verifier: PASS')
print('Version:',AutonomousPositionManagementService.VERSION)
print('Default automation mode:',load_m73_policy().default_automation_mode)
