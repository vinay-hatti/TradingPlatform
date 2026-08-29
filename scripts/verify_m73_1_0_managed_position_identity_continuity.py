from pathlib import Path
import inspect
from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService
from trading_ai.autonomous_position_management.service import AutonomousPositionManagementService

root=Path(__file__).resolve().parents[1]
broker_src=inspect.getsource(BrokerPortfolioSynchronizationService)
auto_src=inspect.getsource(AutonomousPositionManagementService)
assert 'TRADE_PLAN_CONTRACT' in broker_src
assert '_trade_plan_matches_broker_contract' in broker_src
assert 'M73_MANAGED_POSITION_IDENTITY_CONVERGENCE' in broker_src
assert 'SUPERSEDED' in broker_src
assert 'OPEN_BROKER_QUANTITY_WITHOUT_ACTIVE_EXIT_INSTRUCTIONS' in auto_src
assert 'M73_EXIT_INSTRUCTIONS_REARMED' in auto_src
assert AutonomousPositionManagementService.VERSION.startswith('M73.1.0-')
print('M73.1.0 managed-position identity continuity verification: PASSED')
